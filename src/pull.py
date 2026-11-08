"""Phase 0/1: pull taxonomy, totals, subfield sizes and co-occurrence via group_by.

group_by results are capped at 200 groups (no paging), so each subfield's
co-occurrence call returns only its top-200 co-tagged subfields. We merge both
directions: c_ij = max(c_ij from i's call, c_ji from j's call).
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from src.openalex import OpenAlex, short_id

log = logging.getLogger("pull")


def pull_taxonomy(oa: OpenAlex) -> pd.DataFrame:
    rows = []
    for s in oa.paginate("/subfields", {"select": "id,display_name,field,domain,works_count"}):
        rows.append({
            "subfield_id": short_id(s["id"]),
            "subfield": s["display_name"],
            "field_id": short_id(s["field"]["id"]),
            "field": s["field"]["display_name"],
            "domain_id": short_id(s["domain"]["id"]),
            "domain": s["domain"]["display_name"],
            "works_count": s.get("works_count"),
        })
    df = pd.DataFrame(rows).sort_values("subfield_id").reset_index(drop=True)
    df.to_parquet(config.PROCESSED / "subfields.parquet", index=False)
    log.info("subfields: %d (fields=%d, domains=%d)", len(df), df.field_id.nunique(), df.domain_id.nunique())
    return df


def pull_totals(oa: OpenAlex) -> pd.DataFrame:
    d = oa.get("/works", {"filter": f"publication_year:{config.YEAR_MIN}-{config.YEAR_MAX}",
                          "group_by": "publication_year"})
    yr = pd.DataFrame([{"year": int(g["key"]), "N": g["count"]} for g in d["group_by"]])
    yr = yr[(yr.year >= config.YEAR_MIN) & (yr.year <= config.YEAR_MAX)].sort_values("year")
    # Also the number of works with at least one topic (the proper denominator for AS).
    d2 = oa.get("/works", {"filter": f"publication_year:{config.YEAR_MIN}-{config.YEAR_MAX},primary_topic.id:!null",
                           "group_by": "publication_year"})
    yt = pd.DataFrame([{"year": int(g["key"]), "N_topic": g["count"]} for g in d2["group_by"]])
    yr = yr.merge(yt, on="year", how="left")
    yr.to_parquet(config.PROCESSED / "year_totals.parquet", index=False)
    rows = []
    for p, (a, b) in config.PERIODS.items():
        sub = yr[(yr.year >= a) & (yr.year <= b)]
        rows.append({"period": p, "N": int(sub.N.sum()), "N_topic": int(sub.N_topic.sum())})
    pt = pd.DataFrame(rows)
    pt.to_parquet(config.PROCESSED / "period_totals.parquet", index=False)
    log.info("period totals:\n%s", pt)
    return pt


def _size_call(oa: OpenAlex, sid: int):
    d = oa.get("/works", {"filter": f"topics.subfield.id:{sid},publication_year:{config.YEAR_MIN}-{config.YEAR_MAX}",
                          "group_by": "publication_year"})
    return [{"subfield_id": sid, "year": int(g["key"]), "n": g["count"]} for g in d["group_by"]]


def _cooc_call(oa: OpenAlex, sid: int, period: str):
    a, b = config.PERIODS[period]
    d = oa.get("/works", {"filter": f"topics.subfield.id:{sid},publication_year:{a}-{b}",
                          "group_by": "topics.subfield.id", "per_page": 200})
    out = [{"period": period, "src": sid, "dst": short_id(g["key"]), "c": g["count"]} for g in d["group_by"]]
    return out, d["meta"].get("groups_count")


def _run_parallel(oa, fn, jobs, label):
    results, done = [], 0
    with ThreadPoolExecutor(max_workers=config.MAX_THREADS) as ex:
        futs = {ex.submit(fn, oa, *j): j for j in jobs}
        for f in as_completed(futs):
            results.append(f.result())
            done += 1
            if done % 100 == 0 or done == len(jobs):
                log.info("%s: %d/%d  (%s)", label, done, len(jobs), oa.summary())
    return results


def pull_sizes(oa: OpenAlex, subfield_ids: list[int]) -> pd.DataFrame:
    res = _run_parallel(oa, _size_call, [(s,) for s in subfield_ids], "sizes")
    df = pd.DataFrame([r for rs in res for r in rs])
    df = df[(df.year >= config.YEAR_MIN) & (df.year <= config.YEAR_MAX)]
    df = df.sort_values(["subfield_id", "year"]).reset_index(drop=True)
    df.to_parquet(config.PROCESSED / "subfield_year_counts.parquet", index=False)
    return df


def pull_cooc(oa: OpenAlex, subfield_ids: list[int], periods: list[str]) -> pd.DataFrame:
    jobs = [(s, p) for p in periods for s in subfield_ids]
    res = _run_parallel(oa, _cooc_call, jobs, "cooc")
    raw = pd.DataFrame([r for rs, _ in res for r in rs])
    truncated = sum(1 for _, gc in res if gc and gc >= 200)
    log.info("cooc calls truncated at 200 groups: %d/%d", truncated, len(res))
    raw.to_parquet(config.PROCESSED / "cooc_directed.parquet", index=False)

    raw = raw[raw.src != raw.dst]
    raw = raw[raw.src.isin(subfield_ids) & raw.dst.isin(subfield_ids)]
    raw["i"] = raw[["src", "dst"]].min(axis=1)
    raw["j"] = raw[["src", "dst"]].max(axis=1)
    raw["dir"] = (raw.src == raw.i).map({True: "c_ij_from_i", False: "c_ij_from_j"})
    wide = raw.pivot_table(index=["period", "i", "j"], columns="dir", values="c", aggfunc="max").reset_index()
    for col in ["c_ij_from_i", "c_ij_from_j"]:
        if col not in wide:
            wide[col] = pd.NA
    wide["c"] = wide[["c_ij_from_i", "c_ij_from_j"]].max(axis=1).astype(int)
    wide.columns.name = None
    wide.to_parquet(config.PROCESSED / "cooc.parquet", index=False)
    return wide


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=["taxonomy", "totals", "sizes", "cooc", "all"], default="all")
    ap.add_argument("--periods", default=",".join(config.PERIOD_ORDER))
    ap.add_argument("--top", type=int, default=0, help="keep only the N largest subfields (0 = all)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    oa = OpenAlex()

    if args.step in ("taxonomy", "all"):
        sf = pull_taxonomy(oa)
    else:
        sf = pd.read_parquet(config.PROCESSED / "subfields.parquet")
    if args.top:
        sf = sf.nlargest(args.top, "works_count")
    ids = sf.subfield_id.tolist()

    if args.step in ("totals", "all"):
        pull_totals(oa)
    if args.step in ("sizes", "all"):
        pull_sizes(oa, ids)
    if args.step in ("cooc", "all"):
        pull_cooc(oa, ids, args.periods.split(","))
    log.info("done: %s", oa.summary())


if __name__ == "__main__":
    main()
