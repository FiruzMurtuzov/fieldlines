"""Phase 2: association strength, growth, acceleration, interdisciplinarity."""
from __future__ import annotations

import itertools
import logging

import numpy as np
import pandas as pd

import config

log = logging.getLogger("metrics")
P = config.PERIOD_ORDER


def load_inputs():
    sf = pd.read_parquet(config.PROCESSED / "subfields.parquet")
    yc = pd.read_parquet(config.PROCESSED / "subfield_year_counts.parquet")
    pt = pd.read_parquet(config.PROCESSED / "period_totals.parquet").set_index("period")
    cooc = pd.read_parquet(config.PROCESSED / "cooc.parquet")
    return sf, yc, pt, cooc


def period_of(year: int) -> str | None:
    for p, (a, b) in config.PERIODS.items():
        if a <= year <= b:
            return p
    return None


def subfield_period_sizes(yc: pd.DataFrame) -> pd.DataFrame:
    yc = yc.assign(period=yc.year.map(period_of))
    n = yc.groupby(["subfield_id", "period"]).n.sum().unstack("period").reindex(columns=P).fillna(0)
    return n  # index subfield_id, columns P1..P5


def compute_subfield_metrics(sf, n, pt, cooc) -> pd.DataFrame:
    df = sf.set_index("subfield_id")[["subfield", "field_id", "field", "domain_id", "domain"]].copy()
    df = df.loc[df.index.intersection(n.index)]
    for p in P:
        df[f"n_{p}"] = n[p]
        df[f"share_{p}"] = n[p] / pt.loc[p, "N_topic"]
    g = lambda a, b: (df[f"n_{b}"] + 1) / (df[f"n_{a}"] + 1) - 1
    df["growth_P3_P5"] = g("P3", "P5")
    df["growth_P3_P4"] = g("P3", "P4")
    df["growth_P4_P5"] = g("P4", "P5")
    df["acceleration"] = df.growth_P4_P5 - df.growth_P3_P4
    df["share_growth_P3_P5"] = df.share_P5 / df.share_P3.replace(0, np.nan) - 1

    # Interdisciplinarity: share of co-tags outside own field, per period.
    field_of = df.field_id
    c = cooc[["period", "i", "j", "c"]]
    both = pd.concat([c.rename(columns={"i": "a", "j": "b"}), c.rename(columns={"j": "a", "i": "b"})])
    both = both[both.a.isin(field_of.index) & both.b.isin(field_of.index)]
    both["outside"] = both.a.map(field_of).values != both.b.map(field_of).values
    tot = both.groupby(["a", "period"]).c.sum()
    out = both[both.outside].groupby(["a", "period"]).c.sum()
    inter = (out / tot).unstack("period").reindex(columns=P)
    for p in P:
        df[f"interdisc_{p}"] = inter[p] if p in inter else np.nan
    df["established"] = df[f"n_P3"] >= config.MIN_SUBFIELD_SIZE
    return df.reset_index().rename(columns={"index": "subfield_id"})


def compute_pair_metrics(sm: pd.DataFrame, pt, cooc) -> pd.DataFrame:
    ids = sorted(sm.subfield_id)
    pairs = pd.DataFrame(list(itertools.combinations(ids, 2)), columns=["i", "j"])
    grid = pairs.merge(pd.DataFrame({"period": P}), how="cross")
    grid = grid.merge(cooc[["period", "i", "j", "c"]], on=["period", "i", "j"], how="left")
    grid["c"] = grid.c.fillna(0).astype(int)
    grid["observed"] = grid.c > 0

    s = sm.set_index("subfield_id")
    nlong = s[[f"n_{p}" for p in P]].rename(columns=lambda c: c[2:]).stack().rename("n")
    nlong.index.names = ["sid", "period"]
    nmap = nlong.to_dict()
    grid["n_i"] = [nmap.get((i, p), 0) for i, p in zip(grid.i, grid.period)]
    grid["n_j"] = [nmap.get((j, p), 0) for j, p in zip(grid.j, grid.period)]
    grid["N"] = grid.period.map(pt.N_topic)
    grid["AS"] = (grid.c + 1) * grid.N / ((grid.n_i + 1) * (grid.n_j + 1))
    grid["logAS"] = np.log(grid.AS)

    grid = grid.sort_values(["i", "j", "period"]).reset_index(drop=True)
    g = grid.groupby(["i", "j"], sort=False)
    grid["d_logAS"] = g.logAS.diff()
    grid["d_c"] = g.c.diff()

    for col in ["field_id", "domain_id", "subfield", "field", "domain"]:
        grid[f"{col}_i"] = grid.i.map(s[col])
        grid[f"{col}_j"] = grid.j.map(s[col])
    grid["same_field"] = grid.field_id_i == grid.field_id_j
    grid["same_domain"] = grid.domain_id_i == grid.domain_id_j
    return grid


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    sf, yc, pt, cooc = load_inputs()
    n = subfield_period_sizes(yc)
    sm = compute_subfield_metrics(sf, n, pt, cooc)
    sm.to_parquet(config.PROCESSED / "subfield_metrics.parquet", index=False)
    pm = compute_pair_metrics(sm, pt, cooc)
    pm.to_parquet(config.PROCESSED / "pair_metrics.parquet", index=False)

    pd.set_option("display.width", 200)
    em = sm[sm.n_P5 >= config.MIN_SUBFIELD_SIZE].nlargest(10, "acceleration")
    print("\nTop 10 emerging subfields (acceleration, n_P5 >= %d):" % config.MIN_SUBFIELD_SIZE)
    print(em[["subfield", "field", "n_P3", "n_P4", "n_P5", "growth_P3_P4", "growth_P4_P5", "acceleration"]].to_string(index=False))

    cross = pm[(pm.period == "P5") & ~pm.same_field & (pm.c >= config.LABEL_MIN_COUNT)]
    # Rise over two periods (P3 -> P5) for robustness.
    p3 = pm[pm.period == "P3"].set_index(["i", "j"]).logAS
    cross = cross.assign(rise_P3_P5=cross.set_index(["i", "j"]).logAS.values - p3.reindex(cross.set_index(["i", "j"]).index).values)
    print("\nTop 10 fastest-rising cross-field pairs (Δ log AS P3→P5, c_P5 >= %d):" % config.LABEL_MIN_COUNT)
    print(cross.nlargest(10, "rise_P3_P5")[["subfield_i", "subfield_j", "c", "logAS", "rise_P3_P5"]].to_string(index=False))


if __name__ == "__main__":
    main()
