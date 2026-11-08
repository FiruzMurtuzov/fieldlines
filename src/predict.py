"""Phase 4: link prediction (weak cross-field pair -> take-off two periods later) and backtest."""
from __future__ import annotations

import json
import logging

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import config

log = logging.getLogger("predict")
P = config.PERIOD_ORDER
FEATURES = [
    "log_c", "logAS", "d_logAS",
    "log_n_min", "log_n_max", "growth_min", "growth_max", "accel_min", "accel_max",
    "common_nbrs", "adamic_adar", "jaccard",
    "same_comm", "diff_domain", "log_pref_attach",
]
FEATURE_LABELS = {
    "log_c": "current overlap (papers)", "logAS": "current association strength",
    "d_logAS": "recent rise in association", "log_n_min": "size of smaller field",
    "log_n_max": "size of larger field", "growth_min": "growth of slower field",
    "growth_max": "growth of faster field", "accel_min": "acceleration of slower field",
    "accel_max": "acceleration of faster field", "common_nbrs": "shared neighbour fields",
    "adamic_adar": "Adamic–Adar (shared rare neighbours)", "jaccard": "neighbourhood overlap (Jaccard)",
    "same_comm": "same network community", "diff_domain": "different domains",
    "log_pref_attach": "preferential attachment (size product)",
}


def _graph(period: str) -> tuple[nx.Graph, dict]:
    e = pd.read_parquet(config.PROCESSED / f"edges_{period}.parquet")
    nodes = pd.read_parquet(config.PROCESSED / f"nodes_{period}.parquet")
    G = nx.Graph()
    G.add_nodes_from(nodes.subfield_id)
    G.add_edges_from(zip(e.i, e.j))
    return G, nodes.set_index("subfield_id").community.to_dict()


def candidates(pm: pd.DataFrame, sm: pd.DataFrame, t: str) -> pd.DataFrame:
    """Weak cross-field pairs at period t with both subfields above min size."""
    k = P.index(t)
    s = sm.set_index("subfield_id")
    d = pm[pm.period == t].copy()
    d = d[~d.same_field & (d.n_i >= config.MIN_SUBFIELD_SIZE) & (d.n_j >= config.MIN_SUBFIELD_SIZE)]
    med = d.c.median()
    d = d[d.c < med].copy()

    # Momentum from t-1 (0 if t is the first period).
    if k == 0:
        d["d_logAS"] = 0.0
    d["d_logAS"] = d.d_logAS.fillna(0.0)

    def growth(a, b):
        return (s[f"n_{b}"] + 1) / (s[f"n_{a}"] + 1) - 1

    g_t = growth(P[k - 1], t) if k >= 1 else pd.Series(0.0, index=s.index)
    g_prev = growth(P[k - 2], P[k - 1]) if k >= 2 else pd.Series(0.0, index=s.index)
    acc = g_t - g_prev if k >= 2 else pd.Series(0.0, index=s.index)
    gi, gj = d.i.map(g_t), d.j.map(g_t)
    ai, aj = d.i.map(acc), d.j.map(acc)
    d["growth_min"], d["growth_max"] = np.minimum(gi, gj), np.maximum(gi, gj)
    d["accel_min"], d["accel_max"] = np.minimum(ai, aj), np.maximum(ai, aj)
    d["log_c"] = np.log1p(d.c)
    d["log_n_min"] = np.log(np.minimum(d.n_i, d.n_j))
    d["log_n_max"] = np.log(np.maximum(d.n_i, d.n_j))
    d["log_pref_attach"] = np.log(d.n_i.astype(float) * d.n_j.astype(float))
    d["diff_domain"] = (~d.same_domain).astype(int)

    G, comm = _graph(t)
    pairs = list(zip(d.i, d.j))
    d["common_nbrs"] = [len(list(nx.common_neighbors(G, u, v))) for u, v in pairs]
    d["jaccard"] = [x for _, _, x in nx.jaccard_coefficient(G, pairs)]
    d["adamic_adar"] = [x for _, _, x in nx.adamic_adar_index(G, pairs)]
    d["same_comm"] = [int(comm.get(u) == comm.get(v)) for u, v in pairs]
    d["t"] = t
    return d.reset_index(drop=True)


def add_labels(cand: pd.DataFrame, pm: pd.DataFrame, t: str) -> pd.DataFrame:
    t2 = P[P.index(t) + 2]
    fut = pm[pm.period == t2].set_index(["i", "j"])[["logAS", "c"]].rename(
        columns={"logAS": "logAS_future", "c": "c_future"})
    d = cand.join(fut, on=["i", "j"])
    d["rise"] = d.logAS_future - d.logAS
    thr = d.rise.quantile(1 - config.LABEL_TOP_FRAC)
    d["y"] = ((d.rise >= thr) & (d.c_future >= config.LABEL_MIN_COUNT)).astype(int)
    d["label_period"] = t2
    return d


def precision_at(y: np.ndarray, score: np.ndarray, k: int) -> float:
    idx = np.argsort(-score, kind="stable")[:k]
    return float(y[idx].mean())


def evaluate(name: str, y, score, ks=(10, 20, 50, 100)) -> dict:
    out = {"model": name, "roc_auc": float(roc_auc_score(y, score)), "avg_precision": float(average_precision_score(y, score))}
    for k in ks:
        out[f"p@{k}"] = precision_at(y, score, k)
        out[f"hits@{k}"] = int(round(out[f"p@{k}"] * k))
    return out


def models():
    return {
        "logreg": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", C=0.5, max_iter=2000)),
        "hgb": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                              l2_regularization=1.0, class_weight="balanced", random_state=config.SEED),
    }


def baselines(d: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "pref_attach": d.log_pref_attach.values,
        "current_AS": d.logAS.values,
        "recent_growth": d.d_logAS.values + 1e-6 * d.growth_max.values,
    }


def backtest(train: pd.DataFrame, test: pd.DataFrame, tag: str) -> tuple[list[dict], dict]:
    y = test.y.values
    rows, scores = [], {}
    rng = np.random.default_rng(config.SEED)
    rand = [evaluate("random", y, rng.random(len(y))) for _ in range(200)]
    r = {k: float(np.mean([x[k] for x in rand])) for k in rand[0] if k != "model"}
    rows.append({"model": "random", **r})
    for name, s in baselines(test).items():
        rows.append(evaluate(name, y, s)); scores[name] = s
    for name, m in models().items():
        m.fit(train[FEATURES], train.y)
        s = m.predict_proba(test[FEATURES])[:, 1]
        rows.append(evaluate(name, y, s)); scores[name] = s
    for r in rows:
        r["split"] = tag
    return rows, scores


def pk_curve(y, s, kmax=100):
    order = np.argsort(-s, kind="stable")
    hits = np.cumsum(y[order][:kmax])
    return (hits / np.arange(1, len(hits) + 1)).tolist()


def drivers_logreg(model, X: pd.DataFrame, top=3) -> list[list[str]]:
    scaler, lr = model.named_steps["standardscaler"], model.named_steps["logisticregression"]
    contrib = scaler.transform(X) * lr.coef_[0]
    out = []
    for row in contrib:
        idx = np.argsort(-row)[:top]
        out.append([FEATURES[k] for k in idx if row[k] > 0])
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    pm = pd.read_parquet(config.PROCESSED / "pair_metrics.parquet")
    sm = pd.read_parquet(config.PROCESSED / "subfield_metrics.parquet")

    lab = {t: add_labels(candidates(pm, sm, t), pm, t) for t in ["P1", "P2", "P3"]}
    for t, d in lab.items():
        log.info("t=%s candidates=%d positives=%d (%.1f%%)", t, len(d), d.y.sum(), 100 * d.y.mean())
    test = lab["P3"]

    # Strict: standing in 2018, only labels observable by 2018 (P1 -> P3).
    strict_rows, strict_scores = backtest(lab["P1"], test, "strict (train P1→P3)")
    # Plan variant: train on P1→P3 and P2→P4 (P4 labels come from 2019–21).
    plan_rows, plan_scores = backtest(pd.concat([lab["P1"], lab["P2"]]), test, "plan (train P1→P3, P2→P4)")
    metrics = pd.DataFrame(strict_rows + plan_rows)
    pd.set_option("display.width", 200)
    print(metrics.round(3).to_string(index=False))

    y = test.y.values
    curves = {"strict": {k: pk_curve(y, s) for k, s in strict_scores.items()},
              "plan": {k: pk_curve(y, s) for k, s in plan_scores.items()},
              "random_base_rate": float(y.mean())}

    # Pick the headline model: best p@20 on the strict split among the two ML models.
    ml = metrics[(metrics.split.str.startswith("strict")) & metrics.model.isin(["logreg", "hgb"])]
    best = ml.sort_values(["p@20", "avg_precision"], ascending=False).iloc[0].model
    base = metrics[(metrics.split.str.startswith("strict")) & metrics.model.isin(["current_AS", "pref_attach", "recent_growth"])]
    best_base = base.sort_values("p@20", ascending=False).iloc[0]

    top = test.assign(score=strict_scores[best]).nlargest(20, "score")
    top = top[["i", "j", "subfield_i", "subfield_j", "field_i", "field_j", "c", "logAS", "d_logAS",
               "c_future", "logAS_future", "rise", "y", "score"]]
    top.to_parquet(config.PROCESSED / "backtest_top.parquet", index=False)

    # Forecast: retrain on all labelled data, score P5 candidates.
    all_lab = pd.concat(lab.values())
    fc = candidates(pm, sm, "P5")
    m = models()[best]
    m.fit(all_lab[FEATURES], all_lab.y)
    fc["score"] = m.predict_proba(fc[FEATURES])[:, 1]
    lr = models()["logreg"].fit(all_lab[FEATURES], all_lab.y)
    fc["score_logreg"] = lr.predict_proba(fc[FEATURES])[:, 1]
    fc = fc.nlargest(config.FORECAST_TOP_N, "score").reset_index(drop=True)
    fc["drivers"] = [[FEATURE_LABELS[f] for f in fs] for fs in drivers_logreg(lr, fc[FEATURES])]
    keep = ["i", "j", "subfield_i", "subfield_j", "field_i", "field_j", "domain_i", "domain_j",
            "c", "AS", "logAS", "d_logAS", "growth_max", "accel_max", "common_nbrs", "score", "score_logreg", "drivers"]
    fc[keep].to_parquet(config.PROCESSED / "predictions.parquet", index=False)

    coefs = dict(zip(FEATURES, lr.named_steps["logisticregression"].coef_[0].round(3).tolist()))
    out = {
        "headline_model": best,
        "best_baseline": best_base.model,
        "test_candidates": int(len(test)), "test_positives": int(test.y.sum()),
        "base_rate": float(test.y.mean()),
        "train_sizes": {t: int(len(d)) for t, d in lab.items()},
        "metrics": metrics.to_dict(orient="records"),
        "pk_curves": curves,
        "logreg_coefficients": coefs,
        "feature_labels": FEATURE_LABELS,
    }
    json.dump(out, open(config.PROCESSED / "backtest_metrics.json", "w"), indent=1)

    hm = ml.set_index("model").loc[best]
    print(f"\nHeadline ({best}, strict): top 20 had {hm['hits@20']} take-offs vs "
          f"{int(best_base['hits@20'])} for best baseline ({best_base.model}); base rate {test.y.mean():.3f}")
    print("\nBacktest top 20:\n", top[["subfield_i", "subfield_j", "c", "c_future", "rise", "y"]].to_string(index=False))
    print("\nForecast top 10:\n", fc.head(10)[["subfield_i", "subfield_j", "c", "logAS", "d_logAS", "score"]].to_string(index=False))
    print("\nLogReg coefficients:", coefs)


if __name__ == "__main__":
    main()
