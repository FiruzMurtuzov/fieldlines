"""Fieldlines: how scientific disciplines connect, and which pairs are about to take off.

Reads only precomputed files in data/processed/ (no live API calls).
Run: streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

D = config.PROCESSED
PERIODS = config.DISPLAY_PERIODS
PLABEL = {p: f"{a}–{str(b)[2:]}" for p, (a, b) in config.PERIODS.items()}

# Palette (validated: light surface, all pairs; CVD in the warn band, so each domain also
# gets its own marker shape and a legend).
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SURFACE = "#fcfcfb"
DOMAIN_COLOR = {"Physical Sciences": "#2a78d6", "Health Sciences": "#e87ba4",
                "Life Sciences": "#1baf7a", "Social Sciences": "#eda100"}
DOMAIN_SYMBOL = {"Physical Sciences": "circle", "Health Sciences": "square",
                 "Life Sciences": "diamond", "Social Sciences": "triangle-up"}
COMM_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COMM_SYMBOLS = ["circle", "square", "diamond", "triangle-up", "cross", "x", "star", "hexagon"]
MODEL_NAMES = {"hgb": "Fieldlines model (gradient boosting)", "logreg": "Logistic regression",
               "current_AS": "Baseline: current association", "pref_attach": "Baseline: field sizes",
               "recent_growth": "Baseline: recent growth only"}

st.set_page_config(page_title="Fieldlines", page_icon="🧭", layout="wide")


def base_layout(fig: go.Figure, height=420, **kw):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=36, b=8), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK2, size=13),
        hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(color=INK)), **kw)
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig


# ---------------------------------------------------------------- data
@st.cache_data
def load(stamp: float):
    sm = pd.read_parquet(D / "subfield_metrics.parquet")
    yc = pd.read_parquet(D / "subfield_year_counts.parquet")
    nodes = {p: pd.read_parquet(D / f"nodes_{p}.parquet") for p in PERIODS}
    edges = {p: pd.read_parquet(D / f"edges_{p}.parquet") for p in PERIODS}
    bridges = pd.read_parquet(D / "bridges.parquet")
    layout = {int(k): v for k, v in json.load(open(D / "layout.json")).items()}
    preds = pd.read_parquet(D / "predictions.parquet")
    bt = json.load(open(D / "backtest_metrics.json"))
    bt_top = pd.read_parquet(D / "backtest_top.parquet")
    rising = pd.read_parquet(D / "rising_pairs.parquet") if (D / "rising_pairs.parquet").exists() else None
    expl = json.load(open(D / "explanations.json")) if (D / "explanations.json").exists() else {"cards": []}
    totals = pd.read_parquet(D / "period_totals.parquet")
    return sm, yc, nodes, edges, bridges, layout, preds, bt, bt_top, rising, expl, totals


_stamp = max(f.stat().st_mtime for f in D.glob("*") if f.is_file())  # reload when files change
sm, yc, nodes, edges, bridges, layout, preds, bt, bt_top, rising, expl, totals = load(stamp=_stamp)
names = sm.set_index("subfield_id").subfield.to_dict()
metrics = pd.DataFrame(bt["metrics"])
strict = metrics[metrics.split.str.startswith("strict (")].set_index("model")
H = bt["headline_model"]

# ---------------------------------------------------------------- header
st.title("Fieldlines")
st.markdown("How scientific disciplines connect, where new bridges are forming, and which pairs of fields "
            "are most likely to become the next interdisciplinary research area.  \n"
            f"<span style='color:{INK2}'>250 OpenAlex subfields · journal articles and reviews 2010–2024 · "
            f"{int(totals[totals.period.isin(PERIODS)].N_topic.sum() / 1e6)}M papers</span>",
            unsafe_allow_html=True)

tabs = st.tabs(["🗺️ Map", "📈 Emerging", "🌉 Bridges", "🔮 Next big things", "✅ Proof"])

# ---------------------------------------------------------------- 1. Map
with tabs[0]:
    c1, c2, c3 = st.columns([3, 1.3, 1.3])
    period = c1.select_slider("Period", options=PERIODS, value="P5", format_func=lambda p: PLABEL[p])
    color_by = c2.radio("Colour nodes by", ["Domain", "Community"], horizontal=True)
    show_bridges = c3.toggle("Highlight rising bridges", value=True)

    nd = nodes[period].copy()
    nd["x"] = nd.subfield_id.map(lambda s: layout[s][0])
    nd["y"] = nd.subfield_id.map(lambda s: layout[s][1])
    ed = edges[period]
    pos = nd.set_index("subfield_id")[["x", "y"]]

    fig = go.Figure()
    # Edges binned into 3 widths by log AS (one trace per bin keeps the figure light).
    q = ed.weight.quantile([0.5, 0.85]).values
    for lo, hi, w, a in [(-np.inf, q[0], 0.4, 0.10), (q[0], q[1], 0.8, 0.16), (q[1], np.inf, 1.4, 0.26)]:
        e = ed[(ed.weight > lo) & (ed.weight <= hi)]
        xs, ys = [], []
        for i, j in zip(e.i, e.j):
            if i in pos.index and j in pos.index:
                xs += [pos.at[i, "x"], pos.at[j, "x"], None]
                ys += [pos.at[i, "y"], pos.at[j, "y"], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=w, color=f"rgba(82,81,78,{a})"),
                                   hoverinfo="skip", showlegend=False))
    if show_bridges and period != PERIODS[0]:
        br = bridges[bridges.period == period].nlargest(10, "d_logAS")
        for r in br.itertuples():
            fig.add_trace(go.Scatter(
                x=[pos.at[r.i, "x"], pos.at[r.j, "x"]], y=[pos.at[r.i, "y"], pos.at[r.j, "y"]], mode="lines",
                line=dict(width=2.5, color=INK), showlegend=False, hoverinfo="text",
                text=f"<b>{r.subfield_i} × {r.subfield_j}</b><br>{r.c:,} shared papers · association ×{r.AS:.1f}"
                     f"<br>rose {np.exp(r.d_logAS):.1f}× since the previous period"))

    size = 6 + 26 * np.sqrt(nd.n / nd.n.max())
    groups = (sorted(nd.domain.unique()) if color_by == "Domain" else sorted(nd.community.unique()))
    for gi, g in enumerate(groups):
        m = nd[(nd.domain == g) if color_by == "Domain" else (nd.community == g)]
        col = DOMAIN_COLOR.get(g) if color_by == "Domain" else COMM_COLORS[gi % len(COMM_COLORS)]
        sym = DOMAIN_SYMBOL.get(g) if color_by == "Domain" else COMM_SYMBOLS[gi % len(COMM_SYMBOLS)]
        label = g if color_by == "Domain" else f"Community {g + 1}: " + ", ".join(m.nlargest(2, "n").subfield)
        fig.add_trace(go.Scatter(
            x=m.x, y=m.y, mode="markers", name=label,
            marker=dict(size=size[m.index], color=col, symbol=sym, line=dict(width=1, color=SURFACE)),
            customdata=np.stack([m.subfield, m.field, m.n, m.community + 1, m.participation, m.betweenness], axis=1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]:,} papers"
                          "<br>community %{customdata[3]} · participation %{customdata[4]:.2f}"
                          " · betweenness %{customdata[5]:.3f}<extra></extra>"))
    base_layout(fig, height=640, legend=dict(orientation="h", y=-0.02, font=dict(color=INK2)),
                title=dict(text=f"Disciplines in {PLABEL[period]}: {len(ed):,} links stronger than chance",
                           font=dict(color=INK, size=15)))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x")
    st.plotly_chart(fig, width="stretch")
    st.caption("Each node is a subfield, sized by papers in the period. A link means the two subfields share more "
               "papers than their sizes predict (association strength > 1, at least 20 papers). Positions are fixed "
               "across periods. Black lines are the 10 cross-community links that strengthened most since the "
               "previous period.")

# ---------------------------------------------------------------- 2. Emerging
with tabs[1]:
    # Spotlight: one subfield's growth and its fastest-rising partners (AI by default).
    st.subheader("Spotlight")
    big = sm[(sm.n_P3 >= config.MIN_SUBFIELD_SIZE) & ~sm.artifact].copy()
    big["growth_rank"] = big.growth_P3_P5.rank(ascending=False, method="min").astype(int)
    opts = sorted(big.subfield)
    focus = st.selectbox("Subfield", opts, index=opts.index("Artificial Intelligence")
                         if "Artificial Intelligence" in opts else 0)
    fr = big[big.subfield == focus].iloc[0]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Papers 2016–18", f"{int(fr.n_P3):,}")
    k2.metric("Papers 2022–24", f"{int(fr.n_P5):,}", f"{fr.growth_P3_P5:+.0%}")
    k3.metric("Growth rank", f"#{fr.growth_rank} of {len(big)}")
    k4.metric("Share of papers outside its field", f"{fr.interdisc_P5:.0%}",
              f"{(fr.interdisc_P5 - fr.interdisc_P3) * 100:+.1f} pts since 2016–18")
    c_left, c_right = st.columns([1, 1.2])
    with c_left:
        s_ = yc[(yc.subfield_id == fr.subfield_id) & (yc.year >= 2010)]
        f = go.Figure(go.Scatter(x=s_.year, y=s_.n, mode="lines+markers", line=dict(width=2, color="#2a78d6"),
                                 marker=dict(size=8, color="#2a78d6", line=dict(width=2, color=SURFACE)),
                                 hovertemplate="%{x}: %{y:,} papers<extra></extra>"))
        base_layout(f, height=320, title=dict(text=f"{focus}: papers per year", font=dict(color=INK, size=14)),
                    showlegend=False)
        f.update_yaxes(rangemode="tozero")
        st.plotly_chart(f, width="stretch")
    with c_right:
        st.markdown(f"**Where {focus} is spreading fastest** (other fields, 2016–18 → 2022–24)")
        if rising is not None:
            rf = rising[(rising.i == fr.subfield_id) | (rising.j == fr.subfield_id)].copy()
            rf["Partner"] = np.where(rf.i == fr.subfield_id, rf.subfield_j, rf.subfield_i)
            rf["Partner field"] = np.where(rf.i == fr.subfield_id, rf.field_j, rf.field_i)
            rf["rise"] = np.exp(rf.rise_P3_P5)
            st.dataframe(rf.head(12)[["Partner", "Partner field", "c_P3", "c", "rise"]].rename(columns={
                "c_P3": "Papers 2016–18", "c": "Papers 2022–24", "rise": "Association rose ×"}),
                hide_index=True, width="stretch", height=320,
                column_config={"Association rose ×": st.column_config.NumberColumn(format="%.1f×")})

    st.divider()
    rank_by = st.radio("Rank subfields by", ["Growth", "Acceleration"], horizontal=True,
                       help="Growth: papers 2022–24 vs 2016–18. Acceleration: latest growth minus previous "
                            "growth, which favours fields that recently sped up.")
    col = "growth_P3_P5" if rank_by == "Growth" else "acceleration"
    st.subheader("Fastest-growing subfields" if rank_by == "Growth" else "Fastest-accelerating subfields")
    st.caption(("Growth = papers in 2022–24 vs 2016–18. " if rank_by == "Growth" else
                "Acceleration = growth 2019–21 → 2022–24 minus growth 2016–18 → 2019–21. ")
               + f"Subfields with at least {config.MIN_SUBFIELD_SIZE:,} papers in 2016–18.")
    em = big.nlargest(config.EMERGING_TOP_N, col)
    tbl = em[["subfield", "field", "n_P3", "n_P4", "n_P5", "growth_P3_P5", "growth_P3_P4", "growth_P4_P5",
              "acceleration"]].rename(
        columns={"subfield": "Subfield", "field": "Field", "n_P3": "2016–18", "n_P4": "2019–21", "n_P5": "2022–24",
                 "growth_P3_P5": "Growth (6 yrs)", "growth_P3_P4": "Growth (prev 3 yrs)",
                 "growth_P4_P5": "Growth (latest 3 yrs)", "acceleration": "Acceleration"})
    st.dataframe(tbl, hide_index=True, width="stretch", column_config={
        c: st.column_config.NumberColumn(format="%d") for c in ["2016–18", "2019–21", "2022–24"]} | {
        c: st.column_config.NumberColumn(format="percent")
        for c in ["Growth (6 yrs)", "Growth (prev 3 yrs)", "Growth (latest 3 yrs)"]} | {
        "Acceleration": st.column_config.NumberColumn(format="%+.2f")})

    pick = st.multiselect("Papers per year for", options=em.subfield.tolist(), default=em.subfield.tolist()[:3],
                          max_selections=6)
    if pick:
        ids = sm[sm.subfield.isin(pick)].set_index("subfield").subfield_id
        cols = st.columns(min(3, len(pick)))
        for k, name in enumerate(pick):
            s_ = yc[(yc.subfield_id == ids[name]) & (yc.year >= 2010)]
            f = go.Figure(go.Scatter(x=s_.year, y=s_.n, mode="lines+markers", line=dict(width=2, color="#2a78d6"),
                                     marker=dict(size=8, color="#2a78d6", line=dict(width=2, color=SURFACE)),
                                     hovertemplate="%{x}: %{y:,} papers<extra></extra>"))
            base_layout(f, height=230, title=dict(text=name, font=dict(color=INK, size=13)), showlegend=False)
            f.update_yaxes(rangemode="tozero")
            cols[k % len(cols)].plotly_chart(f, width="stretch")
    if rising is not None:
        st.subheader("Fastest-rising cross-field pairs, 2016–18 → 2022–24")
        st.caption("Pairs that already shared at least 20 papers in 2016–18 and at least 50 in 2022–24, "
                   "ranked by how much their association (overlap vs expected) rose.")
        r = rising.head(20).assign(rise=lambda d: np.exp(d.rise_P3_P5))
        st.dataframe(r[["subfield_i", "subfield_j", "c_P3", "c", "rise"]].rename(columns={
            "subfield_i": "Subfield A", "subfield_j": "Subfield B", "c_P3": "Shared papers 2016–18",
            "c": "Shared papers 2022–24", "rise": "Association rose ×"}), hide_index=True, width="stretch",
            column_config={"Association rose ×": st.column_config.NumberColumn(format="%.1f×")})

# ---------------------------------------------------------------- 3. Bridges
with tabs[2]:
    bp = st.select_slider("Period ", options=PERIODS, value="P5", format_func=lambda p: PLABEL[p], key="bp")
    n = nodes[bp][~nodes[bp].subfield_id.isin(list(config.ARTIFACT_SUBFIELDS))].copy()
    n["bridge_score"] = n.participation.rank(pct=True) + n.betweenness.rank(pct=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Bridge subfields")
        st.caption("Participation: how evenly a subfield's links spread across communities (0 = all in one). "
                   "Betweenness: how often it lies on the shortest path between other subfields.")
        top = n.nlargest(15, "bridge_score")
        st.dataframe(top[["subfield", "field", "participation", "betweenness", "degree"]].rename(columns={
            "subfield": "Subfield", "field": "Field", "participation": "Participation",
            "betweenness": "Betweenness", "degree": "Links"}), hide_index=True, width="stretch",
            column_config={"Participation": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                           "Betweenness": st.column_config.NumberColumn(format="%.3f")})
    with right:
        st.subheader("Rising cross-community links")
        st.caption("Links between different communities whose association strength rose most since the previous period.")
        if bp == PERIODS[0]:
            st.info("Pick a later period to see changes.")
        else:
            b = bridges[bridges.period == bp].nlargest(15, "d_logAS").assign(rise=lambda d: np.exp(d.d_logAS))
            st.dataframe(b[["subfield_i", "subfield_j", "c", "rise"]].rename(columns={
                "subfield_i": "Subfield A", "subfield_j": "Subfield B", "c": "Shared papers",
                "rise": "Rose ×"}), hide_index=True, width="stretch",
                column_config={"Rose ×": st.column_config.NumberColumn(format="%.1f×")})

# ---------------------------------------------------------------- 4. Next big things
def paper_link(p):
    url = p.get("doi") or f"https://openalex.org/{p['id']}"
    return f"[{p['title']}]({url}) ({p['year']}, {p['cited_by']:,} citations)"


with tabs[3]:
    st.subheader("The next interdisciplinary research areas")
    st.caption("Pairs of fields that are under-connected today (fewer shared papers than their sizes predict) but "
               "that our model, trained only on past take-offs, ranks most likely to take off by about 2030. "
               "Area names and summaries are written by Gemini from the listed papers only.")
    cards = {(c["i"], c["j"]): c for c in expl.get("cards", []) if c["kind"] == "forecast"}
    for r in preds.head(10).itertuples():
        c = cards.get((r.i, r.j))
        title = c["card"]["area_name"] if c else f"{r.subfield_i} × {r.subfield_j}"
        with st.container(border=True):
            h1, h2 = st.columns([5, 1])
            h1.markdown(f"#### {r.rank}. {title}")
            h1.markdown(f"**{r.subfield_i}** <span style='color:{MUTED}'>({r.field_i})</span> × "
                        f"**{r.subfield_j}** <span style='color:{MUTED}'>({r.field_j})</span>", unsafe_allow_html=True)
            h2.metric("Take-off score", f"{r.score:.2f}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Shared papers 2022–24", f"{r.c:,}")
            m2.metric("Overlap vs expected from field sizes", f"{r.AS:.0%}" if r.AS >= 0.01 else f"{r.AS:.1%}")
            m3.metric("Change since 2019–21", f"×{np.exp(r.d_logAS):.1f}")
            if c:
                cd = c["card"]
                st.markdown(cd["connection"])
                st.markdown(f"**Why now:** {cd['why_now']}")
                st.markdown("**Open questions:**\n" + "\n".join(f"- {q}" for q in cd["open_questions"]))
                byid = {p["id"]: p for p in c["papers"]}
                st.markdown("**Bridge papers:**\n" + "\n".join(f"- {paper_link(byid[i])}" for i in cd["bridge_paper_ids"]
                                                               if i in byid))
            else:
                st.caption("Gemini summary not generated yet.")
            st.caption("Main drivers: " + ", ".join(r.drivers))

# ---------------------------------------------------------------- 5. Proof
with tabs[4]:
    hm, base = strict.loc[H], bt["base_rate"]
    best_base = strict.loc[["current_AS", "pref_attach", "recent_growth"], "hits@100"].max()
    st.subheader("Would it have worked? A backtest standing in 2018")
    k1, k2, k3 = st.columns(3)
    rnd100 = strict.loc["random", "hits@100"]
    k1.metric("Take-offs in our top 100", f"{int(hm['hits@100'])}", f"{hm['hits@100'] / rnd100:.1f}× chance")
    k2.metric("Expected by chance", f"{rnd100:.1f}")
    k3.metric("Best naive baseline", f"{int(best_base)}")
    st.markdown(
        f"Using only papers up to **2018**, the model ranked {bt['test_candidates']:,} under-connected pairs of fields. "
        f"By 2022–24, {bt['test_positives']} of them ({100 * base:.1f}%) had taken off: their association jumped into the "
        f"top 10% and they shared at least {config.LABEL_MIN_COUNT} papers. The model's top 20 contained "
        f"**{int(hm['hits@20'])}**, against {strict.loc['current_AS', 'hits@20']:.0f} for ranking by current association "
        f"and {strict.loc['pref_attach', 'hits@20']:.0f} for ranking by field size. ROC-AUC {hm['roc_auc']:.2f}. "
        "The model never saw any labels from after 2018.")

    curves = bt["pk_curves"]["strict"]
    ks = np.arange(1, 101)
    f = go.Figure()
    f.add_trace(go.Scatter(x=ks, y=ks * base, mode="lines", name="Random (expected)",
                           line=dict(width=2, color=MUTED, dash="dot"),
                           hovertemplate="top %{x}: %{y:.1f} expected<extra>Random</extra>"))
    show = [(H, "#2a78d6"), ("current_AS", "#eb6834"), ("pref_attach", "#1baf7a")]
    for key, col in show:
        hits = np.round(np.array(curves[key]) * ks).astype(int)
        f.add_trace(go.Scatter(x=ks, y=hits, mode="lines", name=MODEL_NAMES[key], line=dict(width=2, color=col),
                               hovertemplate="top %{x}: %{y} take-offs<extra>" + MODEL_NAMES[key] + "</extra>"))
        f.add_annotation(x=100, y=hits[-1], text=f"{hits[-1]}", showarrow=False, xanchor="left", xshift=6,
                         font=dict(color=INK2))
    base_layout(f, height=460, title=dict(text="Take-offs found in the top k ranked pairs (test: 2018 → 2024)",
                                          font=dict(color=INK, size=15)),
                legend=dict(orientation="h", y=-0.3), hovermode="x unified")
    f.update_xaxes(title="k (pairs ranked)", range=[0, 106])
    f.update_yaxes(title="Pairs that took off", rangemode="tozero")
    st.plotly_chart(f, width="stretch")

    t1, t2 = st.columns([1.1, 1])
    with t1:
        st.markdown("**All methods (strict split: trained on labels up to 2018)**")
        mt = strict.reset_index()[["model", "hits@20", "hits@50", "hits@100", "roc_auc", "avg_precision"]]
        mt["model"] = mt.model.map(lambda m: MODEL_NAMES.get(m, "Random (expected)"))
        st.dataframe(mt.rename(columns={"model": "Method", "hits@20": "Top 20", "hits@50": "Top 50",
                                        "hits@100": "Top 100", "roc_auc": "ROC-AUC", "avg_precision": "Avg. precision"}),
                     hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Top 20", "Top 50", "Top 100"]}
                     | {c: st.column_config.NumberColumn(format="%.3f") for c in ["ROC-AUC", "Avg. precision"]})
    with t2:
        st.markdown("**Hits: pairs the model flagged in 2018 that took off**")
        hits = bt_top[bt_top.y == 1].head(15)
        st.dataframe(hits[["rank", "subfield_i", "subfield_j", "c", "c_future"]].rename(columns={
            "rank": "Rank", "subfield_i": "Subfield A", "subfield_j": "Subfield B", "c": "Papers 2016–18",
            "c_future": "Papers 2022–24"}), hide_index=True, width="stretch")
    bcards = [c for c in expl.get("cards", []) if c["kind"] == "backtest"]
    if bcards:
        st.markdown("**What those hits became**")
        for c in bcards:
            with st.expander(f"{c['card']['area_name']}: {c['subfield_i']} × {c['subfield_j']} "
                             f"({c['c_before']} → {c['c_after']:,} papers)"):
                st.markdown(c["card"]["connection"])
                byid = {p["id"]: p for p in c["papers"]}
                st.markdown("\n".join(f"- {paper_link(byid[i])}" for i in c["card"]["bridge_paper_ids"] if i in byid))

    with st.expander("Method and limitations"):
        st.markdown(f"""
- **Data:** OpenAlex (CC0), journal articles and reviews only. Datasets and repository uploads are excluded because they
  flooded 2024 (370k biodiversity records) and added SEO spam that created fake bridges.
- **Link strength:** association strength = observed shared papers ÷ the number expected from the two fields' sizes,
  so giant fields don't connect to everything.
- **Candidates:** cross-field pairs with association < 1 and ≥ {config.CANDIDATE_MIN_C} shared papers.
  **Take-off:** association rise in the top 10% over two periods (six years) *and* ≥ {config.LABEL_MIN_COUNT} shared papers.
- **Limitations:** topics are machine-tagged, so they're noisy. One subfield (Modeling and Simulation) absorbs the
  COVID-19 topics and is excluded from rankings. Some growth reflects OpenAlex covering more journals. Recent papers
  haven't had time to gather citations, so we use topic overlap rather than citations. Growth in overlap is a signal,
  not proof of importance.
""")
