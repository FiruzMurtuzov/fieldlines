"""Phase 3: per-period networks, Louvain communities, bridge scores, fixed layout."""
from __future__ import annotations

import json
import logging

import networkx as nx
import numpy as np
import pandas as pd

import config

log = logging.getLogger("graph")
P = config.PERIOD_ORDER


def edges_for(pm: pd.DataFrame, period: str) -> pd.DataFrame:
    e = pm[(pm.period == period) & (pm.c >= config.EDGE_MIN_COUNT) & (pm.AS > config.EDGE_MIN_AS)].copy()
    e["weight"] = e.logAS
    return e


def build_graph(nodes: pd.DataFrame, e: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(nodes.subfield_id)
    for r in e.itertuples():
        G.add_edge(r.i, r.j, weight=float(r.weight), distance=1.0 / float(r.weight), c=int(r.c))
    return G


def participation(G: nx.Graph, comm: dict[int, int]) -> dict[int, float]:
    out = {}
    for u in G:
        k = G.degree(u, weight="weight")
        if k == 0:
            out[u] = 0.0
            continue
        by = {}
        for v, d in G[u].items():
            by[comm[v]] = by.get(comm[v], 0.0) + d["weight"]
        out[u] = 1.0 - sum((x / k) ** 2 for x in by.values())
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    sm = pd.read_parquet(config.PROCESSED / "subfield_metrics.parquet")
    pm = pd.read_parquet(config.PROCESSED / "pair_metrics.parquet")
    active = sm[sm[[f"n_{p}" for p in P]].min(axis=1) > 0]
    union = nx.Graph()
    union.add_nodes_from(active.subfield_id)
    comm_by_period = {}
    summary = []

    for p in P:
        nodes = active[["subfield_id", "subfield", "field", "domain", f"n_{p}"]].rename(columns={f"n_{p}": "n"})
        e = edges_for(pm, p)
        e = e[e.i.isin(nodes.subfield_id) & e.j.isin(nodes.subfield_id)]
        G = build_graph(nodes, e)
        comms = nx.community.louvain_communities(G, weight="weight", seed=config.SEED)
        comms = sorted(comms, key=len, reverse=True)
        comm = {u: ci for ci, c in enumerate(comms) for u in c}
        comm_by_period[p] = comm
        btw = nx.betweenness_centrality(G, weight="distance", normalized=True)
        part = participation(G, comm)
        nodes = nodes.assign(
            period=p,
            community=nodes.subfield_id.map(comm),
            betweenness=nodes.subfield_id.map(btw),
            participation=nodes.subfield_id.map(part),
            degree=nodes.subfield_id.map(dict(G.degree())),
            strength=nodes.subfield_id.map(dict(G.degree(weight="weight"))),
        )
        nodes.to_parquet(config.PROCESSED / f"nodes_{p}.parquet", index=False)
        ecols = ["i", "j", "c", "AS", "logAS", "d_logAS", "weight", "same_field", "same_domain"]
        e = e[ecols].assign(period=p, cross_comm=[comm[a] != comm[b] for a, b in zip(e.i, e.j)])
        e.to_parquet(config.PROCESSED / f"edges_{p}.parquet", index=False)
        q = nx.community.modularity(G, comms, weight="weight")
        summary.append({"period": p, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                        "communities": len(comms), "modularity": round(q, 3)})
        for r in e.itertuples():
            w = union.get_edge_data(r.i, r.j, {}).get("weight", 0)
            union.add_edge(r.i, r.j, weight=max(w, r.weight))

    # Bridge pairs: cross-community at t, biggest AS rise from t-1.
    names = sm.set_index("subfield_id").subfield
    br = []
    for p in P[1:]:
        e = pd.read_parquet(config.PROCESSED / f"edges_{p}.parquet")
        art = list(config.ARTIFACT_SUBFIELDS)
        e = e[e.cross_comm & ~e.same_field & e.d_logAS.notna() & ~e.i.isin(art) & ~e.j.isin(art)]
        e = e.nlargest(50, "d_logAS").assign(period=p)
        br.append(e)
    br = pd.concat(br)
    br["subfield_i"] = br.i.map(names)
    br["subfield_j"] = br.j.map(names)
    br.to_parquet(config.PROCESSED / "bridges.parquet", index=False)

    pos = nx.spring_layout(union, weight="weight", seed=config.SEED, k=1.2 / np.sqrt(union.number_of_nodes()),
                           iterations=200)
    json.dump({str(k): [float(v[0]), float(v[1])] for k, v in pos.items()},
              open(config.PROCESSED / "layout.json", "w"))
    json.dump(summary, open(config.PROCESSED / "graph_summary.json", "w"), indent=1)

    print(pd.DataFrame(summary).to_string(index=False))
    n5 = pd.read_parquet(config.PROCESSED / "nodes_P5.parquet")
    print("\nTop 10 bridge subfields P5 (participation × betweenness rank):")
    n5["bridge_score"] = n5.participation.rank(pct=True) + n5.betweenness.rank(pct=True)
    print(n5.nlargest(10, "bridge_score")[["subfield", "field", "community", "participation", "betweenness"]].to_string(index=False))
    print("\nTop 10 rising cross-community pairs P5:")
    print(br[br.period == "P5"].nlargest(10, "d_logAS")[["subfield_i", "subfield_j", "c", "logAS", "d_logAS"]].to_string(index=False))


if __name__ == "__main__":
    main()
