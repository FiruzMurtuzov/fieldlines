# Fieldlines — Build Plan

Nov 8, 2026 · @helel

## Goal and pitch

Build **Fieldlines** before the HackTheBurgh submission deadline, 12:00 on Sunday 8 November 2026. Fieldlines maps how scientific disciplines connect over time, finds emerging areas and bridges, and ranks the most likely next interdisciplinary research areas. A backtest shows the method would have worked in the past.

The challenge, as set:

> **11. The Evolution of Scientific Knowledge.** Map how scientific ideas influence one another. Collect research papers and citations. Identify emerging research areas. Track connections between disciplines. Detect ideas that bridge otherwise disconnected fields. Question: can we identify the next important interdisciplinary research area?

**Pitch in one line:** we can't know the future, but we can rank candidates, and a model trained only on data up to 2018 correctly flagged X of the field pairs that took off by 2024.

**Unit of analysis:** OpenAlex subfields (about 250 disciplines), grouped into 3-year periods from 2010 to 2024.

## Ground rules for Claude

Work through the phases in order, and finish each one's "Done when" check before starting the next.

- Commit to git at the end of every phase.
- Precompute everything into `data/processed/`. The app reads only local files, so the demo makes no live API calls.
- Keep keys in `.env` (`OPENALEX_API_KEYS`, comma-separated, and `GEMINI_API_KEY`). Never print or commit them. Add `.env` and `data/raw/` to `.gitignore`.
- Before any bulk pull, make one small test call. Confirm the filter and group\_by field names, and read its cost from the rate-limit response headers. Project the total cost; if it exceeds the remaining budget, shrink the scope (Phase 1 lists how) and tell the team.
- Cache every HTTP response to disk (`requests-cache`, SQLite) so re-runs cost nothing.
- Use APIs only. No scraping.
- Don't hardcode Gemini model names from memory. List the available models with the SDK and pick a current fast "flash" model.
- If a phase runs more than 45 minutes over its slot, apply the next item in the cut list.
- Log key numbers (budget used, backtest metrics, top predictions) in `RESULTS.md` as you go. The pitch is built from it.

## Stack and repo layout

Python 3.11+, with `pandas`, `pyarrow`, `requests` + `requests-cache`, `networkx` (Louvain is built in), `scikit-learn`, `google-genai`, `streamlit`, `plotly` and `python-dotenv`.

```
fieldlines/
  .env.example
  requirements.txt
  config.py              # years, periods, paths, thresholds
  run_all.py             # runs pull → metrics → graph → predict → explain
  src/
    openalex.py          # client: key rotation, cache, backoff, budget tracking
    pull.py              # Phase 1
    metrics.py           # Phase 2
    graph.py             # Phase 3
    predict.py           # Phase 4
    explain.py           # Phase 5
  app/streamlit_app.py   # Phase 6
  data/raw/              # HTTP cache (gitignored)
  data/processed/        # parquet + json the app reads
  RESULTS.md
```

Each pipeline step reads the previous step's files from `data/processed/` and writes its own, so any step can be rerun alone.

## Phase 0: Setup and API checks (20 min)

OpenAlex now requires a free API key for every request and meters use against a daily budget ([docs](https://developers.openalex.org/api-reference/authentication)). Every teammate should create one at openalex.org/settings/api.

1. Create the venv, `requirements.txt` and `.env` from `.env.example`.
2. Build `src/openalex.py`:
   1. Rotate through the keys in `OPENALEX_API_KEYS`, moving to the next on a 429 or exhausted budget.
   2. Cache responses with `requests-cache`.
   3. Retry with exponential backoff (1, 2, 4, 8 s, max 5 tries).
   4. Log the credits used per call from the response headers.
3. Check the remaining budget per key with `GET /rate-limit?api_key=…`.
4. Pull `/domains`, `/fields` and `/subfields` (paginate, `per_page=100`). Save `subfields.parquet` with id, name, field and domain.
5. Make one test co-occurrence call: `/works?filter=topics.subfield.id:1702,publication_year:2019-2021&group_by=topics.subfield.id` Confirm it returns counts of other subfields co-tagged with AI (1702). Check `meta.groups_count` and whether group results need paging. If the field name is rejected, find the correct one in the docs and adapt.
6. Make one trivial Gemini call to test the key.

**Done when:** `subfields.parquet` exists, the test call works, and the cost per call plus the projected Phase 1 cost are written to `RESULTS.md`.

## Phase 1: Data pull (60–75 min, mostly running in the background)

Use `group_by` aggregations so no individual papers need downloading: about 1,500 calls in total.

**Periods:** P1 2010–12, P2 2013–15, P3 2016–18, P4 2019–21, P5 2022–24. Leave 2025 out because its counts are incomplete.

1. **Totals:** `/works?filter=publication_year:2010-2024&group_by=publication_year`. One call gives N per year.
2. **Subfield sizes:** for each subfield S, `/works?filter=topics.subfield.id:S,publication_year:2010-2024&group_by=publication_year`. About 250 calls, giving n\_i per year.
3. **Co-occurrence:** for each subfield S and period, `/works?filter=topics.subfield.id:S,publication_year:A-B&group_by=topics.subfield.id`. About 1,250 calls, giving c\_ij. Drop the diagonal (i = j).

**Running it:** at most 5 threads with a global rate limit. Make it resumable so cached calls are skipped. Spread subfields across teammates' keys.

**If the projected cost is over budget, cut in this order:**

1. Drop P1 and start at 2013.
2. Keep only the 120 largest subfields.
3. Switch to the field level (26 fields) instead of subfields.

**Outputs:** `period_totals.parquet`, `subfield_year_counts.parquet` (subfield, year, n) and `cooc.parquet` (period, i, j, c\_ij, with i < j).

**Done when:** every period has a matrix. Symmetry check: c\_ij and c\_ji agree within a few percent. Spot check: AI's overlap with a biology subfield grows across periods.

## Phase 2: Metrics (45 min)

Normalise every link by what its fields' sizes would predict; otherwise huge fields like medicine and AI connect to everything.

**Association strength** (observed ÷ expected overlap), with +1 smoothing on c\_ij:

```latex
AS_{ij}(p) = \frac{c_{ij}(p) \cdot N(p)}{n_i(p) \cdot n_j(p)}
```

- **Pair metrics:** c\_ij, log AS\_ij, and their change between consecutive periods.
- **Subfield growth:** growth rate of n\_i from P3 to P5, plus acceleration = growth(P4→P5) − growth(P3→P4).
- **Emerging subfields:** top 20 by acceleration among subfields above a minimum size (set the minimum in `config.py`).
- **Interdisciplinarity per subfield:** share of its co-tags that fall outside its own field.

**Outputs:** `subfield_metrics.parquet`, `pair_metrics.parquet`.

**Done when:** printing the top 10 emerging subfields and top 10 fastest-rising cross-field pairs gives plausible results.

## Phase 3: Network, communities and bridges (45 min)

Build one weighted graph per period: nodes are subfields, edges are pairs with c\_ij ≥ 20 and AS\_ij > 1, weighted by log AS\_ij.

1. **Communities:** `networkx.community.louvain_communities(G, weight='weight', seed=42)` per period.
2. **Bridge subfields**, scored per node:
   - weighted betweenness centrality, using distance = 1 / weight
   - participation coefficient: P\_i = 1 − Σ\_s (k\_is / k\_i)², where k\_is is node i's edge weight into community s
3. **Bridge pairs:** pairs whose endpoints sit in different communities and whose AS rose most from the previous period.
4. **Layout:** compute one `spring_layout` on the union of all periods (seed 42) and save the positions, so nodes don't jump around when the app's period slider moves.

**Outputs:** `nodes_{period}.parquet`, `edges_{period}.parquet`, `bridges.parquet`, `layout.json`.

**Done when:** every period has communities and bridge scores, and the top 10 bridges print with readable names.

## Phase 4: Link prediction and backtest (90 min, the core)

Predict which weakly connected pairs of fields become strongly connected two periods (six years) later, and prove it on held-out years.

**Candidates at period t:** pairs from different fields, both above the minimum size, with c\_ij below the median for cross-field pairs.

**Label:** y = 1 if, at t + 2, the pair's rise in log AS is in the top 10% of candidates **and** c\_ij ≥ 50 (so tiny counts don't count as take-offs).

**Splits (no data after the feature period may leak in):**

| Split | Features from | Labels from |
| --- | --- | --- |
| Train | P1 and P2 | P3 and P4 |
| Test ("standing in 2018") | P3 (2016–18) | P5 (2022–24) |
| Forecast | P5 (2022–24) | the future |

**Features,** all computed from data at or before t:

- c\_ij, log AS\_ij, and Δ log AS from t − 1 to t (0 if missing)
- n\_i, n\_j, their growth and acceleration
- common neighbours, Adamic–Adar and Jaccard on the period-t graph
- same-community flag, different-domain flag, preferential attachment (n\_i × n\_j)
- stretch goal: cosine similarity of Gemini embeddings of each subfield's name plus its top topic names

**Models:** logistic regression (scaled, class-weighted) and `HistGradientBoostingClassifier`.

**Baselines:** random, preferential attachment, current AS, recent growth only.

**Metrics on the test split:** precision@20, precision@50, ROC-AUC and average precision. Plot precision@k for the model against each baseline.

**Forecast:** retrain on all labelled data, score the P5 candidates, keep the top 25 (top 10 shown in the app). For each, record its main drivers from the coefficients or feature importances.

**Outputs:** `backtest_metrics.json`, `backtest_top.parquet` (test top 20 with actual outcomes), `predictions.parquet`.

**Done when:** the metrics are in `RESULTS.md` and the model beats the current-AS and preferential-attachment baselines on precision@20. If it doesn't, rank by the best heuristic and say so honestly in the pitch.

## Phase 5: Gemini explanations (45 min)

Turn each of the top 10 forecast pairs, plus the top 3 backtest hits, into a readable card that only references real papers.

1. **Bridge papers:** `/works?filter=topics.subfield.id:A,topics.subfield.id:B,publication_year:2022-2025&sort=cited_by_count:desc&per_page=10&select=id,doi,title,publication_year,cited_by_count,abstract_inverted_index`. Repeating the filter key should mean the paper is tagged with both subfields; verify this in the docs. Rebuild each abstract from its inverted index.
2. **Prompt Gemini** in JSON mode. Give it the two subfield names, their metrics (growth, AS trend) and the 10 papers' titles and abstracts. Ask for:
   - a name for the emerging area, at most 6 words
   - two sentences on what connects the fields
   - one sentence on why now
   - three open research questions
   - the ids of the 3 most bridging papers from the list provided
3. Tell Gemini to use only the papers given. Reject and retry any reply whose paper ids aren't in the fetched list.
4. Cache the results to `explanations.json`.

**Done when:** all 13 explanations are saved and every cited paper id is valid. Using Gemini here also qualifies the project for MLH's Best Use of Gemini API prize.

## Phase 6: Streamlit app (2 hours)

Five tabs, all loading precomputed files with `st.cache_data`. Start the skeleton on mock data while Phase 1 runs.

1. **Map:** a Plotly network of subfields using the fixed layout, with a period slider from P1 to P5. Node colour = domain (toggle to community), size = n\_i, edge width = log AS. Highlight the top bridges, and show name and numbers on hover.
2. **Emerging:** the top 20 subfields by acceleration, with a papers-per-year line chart for selected ones.
3. **Bridges:** the top bridge subfields (participation, betweenness) and rising cross-community pairs.
4. **Next big things:** 10 cards, each showing the Gemini area name, the two subfields, why now, open questions, bridge papers linked to DOI or OpenAlex, and the model score.
5. **Proof:** the headline "Standing in 2018, our top 20 included X pairs that took off by 2024, vs Y for the naive baseline", the precision@k chart, and the list of hits.

**Done when:** `streamlit run app/streamlit_app.py` works from a clean clone using only `data/processed/`. Deploying (Streamlit Community Cloud or a Vultr VM) is optional.

## Timeline and cut list

The last 75 minutes before the 12:00 deadline go to the team (pitch, video, Devpost), so the build must finish by 10:30.

| Time (Sun) | Work |
| --- | --- |
| 02:15–02:35 | Phase 0: setup and API checks |
| 02:35–03:45 | Phase 1: data pull in the background; app skeleton on mock data in parallel |
| 03:45–04:30 | Phase 2: metrics |
| 04:30–05:15 | Phase 3: network and bridges |
| 05:15–06:45 | Phase 4: prediction and backtest |
| 06:45–07:30 | Phase 5: Gemini explanations |
| 07:30–09:30 | Phase 6: app on real data |
| 09:30–10:30 | Polish, README, `RESULTS.md` |
| 10:30–11:45 | Team: pitch, backup video, Devpost |
| 12:00 | Submission deadline |

**If behind, cut in this order:**

1. The embeddings feature.
2. P1, or drop to the field level.
3. Gemini cards for the top 5 instead of 10.
4. The Bridges tab (fold its highlights into Map).
5. Gradient boosting (keep logistic regression and the heuristics).

**Never cut:** the backtest headline and the Next big things tab.

## Definition of done and demo script

- [ ] `python run_all.py` rebuilds `data/processed/` from the cache
- [ ] The app runs offline from processed data
- [ ] `RESULTS.md` has the backtest metrics and the top 10 predictions
- [ ] The README covers the problem, method, data source (OpenAlex, CC0) and limitations
- [ ] A backup screen recording of the demo exists

**Demo script (3 minutes):**

1. **20 s:** the question: can we spot the next interdisciplinary field before it happens?
2. **40 s:** Map tab: slide from 2010 to 2024, watch fields pull together, and point at one bridge.
3. **40 s:** Proof tab: "Standing in 2018, our model's top 20 had X real take-offs, vs Y for the naive baseline."
4. **50 s:** Next big things tab: open two cards and show their bridge papers.
5. **30 s:** limitations and next steps:
   - topics are machine-tagged, so they're noisy
   - recent papers haven't had time to collect citations, so we use topic overlap, not citations
   - growth in overlap is a signal, not proof of importance

## Fallback plan: arXiv metadata

If the OpenAlex budget or API blocks Phase 1 by 03:30, switch to the arXiv metadata dump. Only `pull.py` changes; Phases 2 to 6 stay the same.

1. Download the Kaggle dataset `Cornell-University/arxiv` (JSON lines, a few GB) with the Kaggle CLI. This needs a `kaggle.json` token, so a teammate can start it now as insurance.
2. Nodes = arXiv categories (about 150). Co-occurrence = papers cross-listed in two categories, such as `cs.LG` with `q-bio.BM`. Take each paper's year from its first version date.
3. Bridge papers for Gemini come from the same dump, which includes titles and abstracts.
4. In the pitch, say that coverage is limited to physics, maths, CS, quantitative biology and finance, statistics, electrical engineering and economics.
