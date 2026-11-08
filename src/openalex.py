"""OpenAlex client: key rotation, on-disk cache, exponential backoff, budget tracking.

Keys come from OPENALEX_API_KEYS (comma-separated) in .env. Keys are never logged:
the cache ignores the api_key parameter, and URLs are logged with it stripped.
"""
from __future__ import annotations

import csv
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests
import requests_cache
from dotenv import load_dotenv

import config

load_dotenv(config.ROOT / ".env")
log = logging.getLogger("openalex")


class BudgetExhausted(RuntimeError):
    pass


class _RateLimiter:
    def __init__(self, per_sec: float):
        self.min_interval = 1.0 / per_sec
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_t)
            self.next_t = t + self.min_interval
        if t > now:
            time.sleep(t - now)


class OpenAlex:
    def __init__(self, keys: list[str] | None = None):
        if keys is None:
            raw = os.getenv("OPENALEX_API_KEYS", "")
            keys = [k.strip() for k in raw.split(",") if k.strip()]
        self.keys = keys
        if not self.keys:
            log.warning("No OPENALEX_API_KEYS set: using the shared keyless budget ($0.10/day per IP).")
        self.key_idx = 0
        self.dead_keys: set[int] = set()
        self.lock = threading.Lock()
        self.limiter = _RateLimiter(config.MAX_REQ_PER_SEC)
        self.session = requests_cache.CachedSession(
            str(config.HTTP_CACHE),
            backend="sqlite",
            expire_after=requests_cache.NEVER_EXPIRE,
            allowable_codes=(200,),
            ignored_parameters=["api_key"],
            match_headers=False,
        )
        self.spent_usd = 0.0
        self.calls_live = 0
        self.calls_cached = 0
        self.remaining_usd: dict[int, float] = {}
        self._log_lock = threading.Lock()

    # ---- key handling -------------------------------------------------
    def _current_key(self) -> tuple[int, str | None]:
        with self.lock:
            if not self.keys:
                return -1, None
            if len(self.dead_keys) >= len(self.keys):
                raise BudgetExhausted("All OpenAlex keys are exhausted for today.")
            while self.key_idx in self.dead_keys:
                self.key_idx = (self.key_idx + 1) % len(self.keys)
            return self.key_idx, self.keys[self.key_idx]

    def _kill_key(self, idx: int, reason: str):
        with self.lock:
            if idx >= 0 and idx not in self.dead_keys:
                self.dead_keys.add(idx)
                log.warning("Key #%d retired (%s); %d left", idx, reason, len(self.keys) - len(self.dead_keys))
                self.key_idx = (idx + 1) % len(self.keys)
        if idx < 0:
            raise BudgetExhausted(f"Keyless budget exhausted ({reason}).")

    # ---- logging ------------------------------------------------------
    def _log_budget(self, idx: int, path: str, params: dict, resp: requests.Response):
        h = resp.headers
        cost = float(h.get("x-ratelimit-cost-usd", 0) or 0)
        rem = h.get("x-ratelimit-remaining-usd")
        with self._log_lock:
            self.spent_usd += cost
            if rem is not None:
                self.remaining_usd[idx] = float(rem)
            new = not config.BUDGET_LOG.exists()
            with open(config.BUDGET_LOG, "a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["ts", "key_idx", "path", "params", "status", "cost_usd", "credits", "remaining_usd"])
                safe = {k: v for k, v in params.items() if k != "api_key"}
                w.writerow([datetime.now(timezone.utc).isoformat(), idx, path, safe, resp.status_code,
                            cost, h.get("x-ratelimit-credits-used"), rem])

    # ---- main entry ---------------------------------------------------
    def get(self, path: str, params: dict | None = None, use_cache: bool = True) -> dict:
        params = dict(params or {})
        url = config.OPENALEX_BASE + path
        if use_cache:
            # Cache lookup without spending budget or touching the rate limiter.
            key = self.session.cache.create_key(requests.Request("GET", url, params=params).prepare())
            cached = self.session.cache.get_response(key)
            if cached is not None:
                with self._log_lock:
                    self.calls_cached += 1
                return cached.json()

        attempt = 0
        while True:
            idx, k = self._current_key()
            p = dict(params)
            if k:
                p["api_key"] = k
            self.limiter.wait()
            try:
                if use_cache:
                    resp = self.session.get(url, params=p, timeout=60)
                else:
                    with self.session.cache_disabled():
                        resp = self.session.get(url, params=p, timeout=60)
            except requests.RequestException as e:
                resp, err = None, e
            else:
                err = None

            if resp is not None and not getattr(resp, "from_cache", False):
                self._log_budget(idx, path, params, resp)
                with self._log_lock:
                    self.calls_live += 1

            if resp is not None and resp.status_code == 200:
                return resp.json()

            if resp is not None and resp.status_code == 429:
                # Distinguish short-term throttling from an exhausted daily budget.
                rem = resp.headers.get("x-ratelimit-remaining-usd")
                if rem is not None and float(rem) <= 0:
                    self._kill_key(idx, "daily budget exhausted")
                    continue
                if attempt >= len(config.BACKOFF_SECONDS):
                    self._kill_key(idx, "persistent 429")
                    attempt = 0
                    continue
            elif resp is not None and resp.status_code in (400, 404):
                raise ValueError(f"OpenAlex {resp.status_code} for {path} {params}: {resp.text[:300]}")
            elif resp is not None and resp.status_code in (401, 403):
                self._kill_key(idx, f"HTTP {resp.status_code}")
                continue

            if attempt >= len(config.BACKOFF_SECONDS):
                raise RuntimeError(f"OpenAlex failed after retries: {path} {params}: "
                                   f"{err or (resp.status_code, resp.text[:200])}")
            time.sleep(config.BACKOFF_SECONDS[attempt])
            attempt += 1

    def paginate(self, path: str, params: dict | None = None, per_page: int = 100):
        """Page-number pagination (fine for small lists; cursor paging needs a key)."""
        params = dict(params or {})
        params["per_page"] = per_page
        page = 1
        while True:
            params["page"] = page
            d = self.get(path, params)
            res = d.get("results", [])
            yield from res
            if not res or page * per_page >= d.get("meta", {}).get("count", 0):
                break
            page += 1

    def rate_limit(self) -> list[dict]:
        """Remaining budget per key (uncached)."""
        out = []
        for i, k in enumerate(self.keys or [None]):
            params = {"api_key": k} if k else {}
            with self.session.cache_disabled():
                r = self.session.get(config.OPENALEX_BASE + "/rate-limit", params=params, timeout=30)
            try:
                body = r.json()
            except ValueError:
                body = {"text": r.text[:300]}
            out.append({"key_idx": i if k else -1, "status": r.status_code, "body": body,
                        "remaining_usd": r.headers.get("x-ratelimit-remaining-usd")})
        return out

    def summary(self) -> str:
        return (f"live calls={self.calls_live}, cached={self.calls_cached}, "
                f"spent=${self.spent_usd:.4f}, remaining per key={self.remaining_usd}")


def short_id(openalex_url: str) -> int:
    return int(str(openalex_url).rstrip("/").split("/")[-1])
