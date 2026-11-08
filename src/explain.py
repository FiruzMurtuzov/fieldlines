"""Phase 5: Gemini explanation cards grounded in real bridge papers.

For each top forecast pair (and top backtest hits) fetch the most-cited papers
tagged with BOTH subfields (repeating the filter key = AND, verified: 1,041 for
Aquatic Science x EEE, equal to our c_ij), then ask Gemini for a JSON card that
may only cite those papers. Replies citing unknown ids are rejected and retried.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from dotenv import load_dotenv

import config
from src.openalex import OpenAlex

load_dotenv(config.ROOT / ".env")
log = logging.getLogger("explain")
OUT = config.PROCESSED / "explanations.json"
N_FORECAST, N_BACKTEST = 10, 3


def pick_models(client) -> list[str]:
    """Plain 'gemini-X.Y-flash' models (no lite/image/preview), newest first, as a fallback chain."""
    found = []
    for m in client.models.list():
        name = m.name.removeprefix("models/")
        if "generateContent" not in (m.supported_actions or []):
            continue
        mt = re.fullmatch(r"gemini-(\d+)\.(\d+)-flash", name)
        if mt:
            found.append(((int(mt[1]), int(mt[2])), name))
    if not found:
        raise RuntimeError("No gemini-*-flash model available")
    return [n for _, n in sorted(found, reverse=True)]


def trim_name(name: str, n: int = 6) -> str:
    """At most n words, without a dangling 'and'/'for'/... at the end."""
    w = name.split()[:n]
    while w and w[-1].lower().strip(",;:-") in {"and", "for", "of", "the", "in", "with", "to", "&", "a", "on"}:
        w.pop()
    return " ".join(w)


def rebuild_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = [(p, w) for w, ps in inv.items() for p in ps]
    return " ".join(w for _, w in sorted(pos))


def bridge_papers(oa: OpenAlex, a: int, b: int, years: str = "2022-2025", n: int = 10) -> list[dict]:
    d = oa.get("/works", {
        "filter": f"topics.subfield.id:{a},topics.subfield.id:{b},publication_year:{years},{config.WORK_FILTER}",
        "sort": "cited_by_count:desc", "per_page": n,
        "select": "id,doi,title,publication_year,cited_by_count,abstract_inverted_index",
    })
    out = []
    for w in d["results"]:
        out.append({
            "id": w["id"].rsplit("/", 1)[-1],
            "doi": w.get("doi"),
            "title": (w.get("title") or "").strip(),
            "year": w.get("publication_year"),
            "cited_by": w.get("cited_by_count", 0),
            "abstract": rebuild_abstract(w.get("abstract_inverted_index"))[:1500],
        })
    return out


PROMPT = """You are helping a research-trends tool explain an emerging interdisciplinary area.

Two OpenAlex subfields: "{a}" ({fa}) and "{b}" ({fb}).
Evidence from our analysis of journal articles:
{metrics}

Below are the most-cited recent papers tagged with BOTH subfields. Use ONLY these papers;
do not invent papers, results or facts that are not supported by them.

{papers}

Return JSON with exactly these keys:
- "area_name": a name for the emerging area, at most 6 words
- "connection": two sentences on what connects the two fields, grounded in the papers
- "why_now": one sentence on why this is happening now, about the science (do not mention our model, scores or metrics)
- "open_questions": a list of exactly three open research questions
- "bridge_paper_ids": a list of the ids (like "W123") of the 3 papers above that best bridge the two fields
"""


def fmt_metrics(r: dict) -> str:
    lines = [f"- co-tagged papers: {r['c_before']} in {r['period_before']} -> {r['c_after']} in {r['period_after']}"]
    lines.append(f"- association strength (observed/expected overlap): {r['AS_before']:.2f} -> {r['AS_after']:.2f}")
    if r.get("score") is not None:
        lines.append(f"- model take-off score: {r['score']:.2f}")
    return "\n".join(lines)


def ask(client, models: list[str], r: dict, papers: list[dict], tries: int = 6) -> tuple[dict, str]:
    from google.genai import types
    ptxt = "\n\n".join(f"[{p['id']}] {p['title']} ({p['year']}, {p['cited_by']} citations)\n{p['abstract'] or '(no abstract)'}"
                       for p in papers)
    prompt = PROMPT.format(a=r["subfield_i"], b=r["subfield_j"], fa=r["field_i"], fb=r["field_j"],
                           metrics=fmt_metrics(r), papers=ptxt)
    valid = {p["id"] for p in papers}
    last = None
    for k in range(tries):
        model = models[min(k // 2, len(models) - 1)]  # two tries per model, then fall back
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
            card = json.loads(resp.text)
            ids = card.get("bridge_paper_ids") or []
            keys_ok = all(x in card for x in ["area_name", "connection", "why_now", "open_questions", "bridge_paper_ids"])
            if keys_ok and ids and set(ids) <= valid and len(card["open_questions"]) == 3:
                card["area_name"] = trim_name(card["area_name"])
                return card, model
            last = f"invalid card (ids ok={set(ids) <= valid}, keys ok={keys_ok})"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:200]
        log.warning("retry %d (%s) for %s x %s: %s", k + 1, model, r["subfield_i"], r["subfield_j"], last[:120])
        time.sleep(min(60, 5 * 2 ** k) if ("429" in last or "503" in last) else 2)
    raise RuntimeError(f"Gemini failed for {r['subfield_i']} x {r['subfield_j']}: {last}")


def build_jobs() -> list[dict]:
    pm = pd.read_parquet(config.PROCESSED / "pair_metrics.parquet").set_index(["period", "i", "j"])
    jobs = []
    pr = pd.read_parquet(config.PROCESSED / "predictions.parquet").head(N_FORECAST)
    for r in pr.itertuples():
        p3 = pm.loc[("P3", r.i, r.j)]
        jobs.append({"kind": "forecast", "rank": int(r.rank), "i": int(r.i), "j": int(r.j),
                     "subfield_i": r.subfield_i, "subfield_j": r.subfield_j, "field_i": r.field_i, "field_j": r.field_j,
                     "period_before": "2016–18", "period_after": "2022–24",
                     "c_before": int(p3.c), "c_after": int(r.c), "AS_before": float(p3.AS), "AS_after": float(r.AS),
                     "score": float(r.score), "drivers": list(r.drivers)})
    bt = pd.read_parquet(config.PROCESSED / "backtest_top.parquet")
    bt = bt[bt.y == 1].head(N_BACKTEST)
    for r in bt.itertuples():
        p5 = pm.loc[("P5", r.i, r.j)]
        jobs.append({"kind": "backtest", "rank": None, "i": int(r.i), "j": int(r.j),
                     "subfield_i": r.subfield_i, "subfield_j": r.subfield_j, "field_i": r.field_i, "field_j": r.field_j,
                     "period_before": "2016–18", "period_after": "2022–24",
                     "c_before": int(r.c), "c_after": int(r.c_future), "AS_before": float(pm.loc[("P3", r.i, r.j)].AS),
                     "AS_after": float(p5.AS), "score": float(r.score), "drivers": []})
    return jobs


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=240_000))
    models = pick_models(client)
    log.info("Gemini model chain: %s", models)
    cache = json.load(open(OUT)) if OUT.exists() else {"cards": []}
    done = {(c["i"], c["j"], c["kind"]): c for c in cache["cards"]}

    oa = OpenAlex()
    jobs = build_jobs()
    for jb in jobs:
        jb["papers"] = bridge_papers(oa, jb["i"], jb["j"])

    lock = threading.Lock()

    def save():
        with lock:
            json.dump({"models": models, "cards": list(done.values())}, open(OUT, "w"), indent=1, ensure_ascii=False)

    def run(jb):
        key = (jb["i"], jb["j"], jb["kind"])
        if key in done and done[key].get("papers") == jb["papers"]:
            return done[key]
        try:
            card, model = ask(client, models, jb, jb["papers"])
        except RuntimeError as e:
            log.error("%s", e)
            return None
        log.info("card (%s): %s x %s -> %s", model, jb["subfield_i"], jb["subfield_j"], card["area_name"])
        out = {**jb, "card": card, "model": model}
        with lock:
            done[key] = out
        save()
        return out

    with ThreadPoolExecutor(max_workers=2) as ex:
        cards = [c for c in ex.map(run, jobs) if c]
    log.info("%d/%d cards ok", len(cards), len(jobs))
    for c in cards:
        assert set(c["card"]["bridge_paper_ids"]) <= {p["id"] for p in c["papers"]}
    order = {(jb["i"], jb["j"], jb["kind"]): k for k, jb in enumerate(jobs)}
    cards.sort(key=lambda c: order[(c["i"], c["j"], c["kind"])])
    json.dump({"models": models, "cards": cards}, open(OUT, "w"), indent=1, ensure_ascii=False)
    log.info("saved %d cards (%s)", len(cards), oa.summary())


if __name__ == "__main__":
    main()
