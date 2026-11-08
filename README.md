# Fieldlines

**Can we spot the next interdisciplinary research area before it happens?**

Fieldlines maps how 250 scientific disciplines connect from 2010 to 2024. It finds emerging fields and the subfields that bridge communities, then ranks pairs of fields that are under-connected today but likely to take off. A backtest shows the method would have worked in the past: standing in 2018, its top 100 contained 14 pairs that took off by 2024, about 2.5 times what chance gives (5.6) and well ahead of the naive baselines (2–3).

Built for HackTheBurgh 2026, challenge 11: *The Evolution of Scientific Knowledge*.

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app/streamlit_app.py
```

The app reads only `data/processed/`, which is committed to the repo, so it runs offline with no API keys.

To rebuild the data, copy `.env.example` to `.env` and add free OpenAlex keys plus a Gemini key, then run `python run_all.py`. Every HTTP response is cached in `data/raw/`, so a rebuild from a warm cache takes seconds and costs nothing. From scratch it takes about 1,800 OpenAlex calls (about $0.18 of the free $1/day budget).

## Data

[OpenAlex](https://openalex.org) (CC0). We use `group_by` aggregations only and never download individual papers:

- **Nodes:** the 252 OpenAlex subfields, each in one of 26 fields and 4 domains.
- **Corpus:** journal articles and reviews (`type:article|review, primary_location.source.type:journal`), 2007–2024, grouped into 3-year periods. Before the filter, 2024 was flooded with 370k biodiversity dataset records, and Zenodo SEO spam created fake bridges such as "Materials Science × Anthropology" (664 adverts for funeral supplies).
- **Co-occurrence c_ij:** papers tagged with both subfields i and j. The API caps `group_by` at 200 groups, so each pair is taken as the larger of the counts from i's call and j's call. Where both calls see a pair, the two counts match exactly.

## Method

1. **Association strength:** AS_ij = c_ij · N / (n_i · n_j), with +1 smoothing. This is observed overlap divided by what the two fields' sizes would predict, so giant fields like medicine and AI don't connect to everything.
2. **Emerging subfields:** acceleration of paper growth. **Interdisciplinarity:** the share of a subfield's co-tags that fall outside its own field.
3. **Network:** for each period, an edge wherever c ≥ 20 and AS > 1, weighted by log AS. Louvain communities (6 per period, modularity ≈ 0.50). Bridges are scored by participation coefficient and weighted betweenness. Node positions are fixed across periods.
4. **Link prediction:**
   - *Candidates:* cross-field pairs that are under-connected (AS < 1) but non-trivial (c ≥ 5).
   - *Take-off:* six years later, the rise in log AS is in the top 10% **and** c ≥ 50.
   - *Features:* overlap, AS, momentum, field sizes, growth and acceleration, common neighbours, Adamic–Adar, Jaccard, community and domain flags.
   - *Models:* gradient boosting and logistic regression, compared against preferential-attachment, current-AS and recent-growth baselines.
5. **Strict temporal backtest:** train only on take-offs observable by 2018 (2007–09 → 2013–15 and 2010–12 → 2016–18). Test on features from 2016–18 against outcomes in 2022–24.
6. **Explanations:** for each forecast pair, fetch the most-cited 2022–25 papers tagged with both subfields. Gemini names the area and summarises it, in JSON mode, using only those papers. Any reply that cites a paper ID outside the list is rejected and retried.

Results are in [RESULTS.md](RESULTS.md).

## Layout

```
config.py              years, periods, filters, thresholds
run_all.py             pull → metrics → graph → predict → explain
src/openalex.py        API client: key rotation, SQLite cache, backoff, budget log
src/pull.py            taxonomy, totals, subfield sizes, co-occurrence
src/metrics.py         association strength, growth, acceleration, interdisciplinarity
src/graph.py           networks, Louvain, bridges, layout
src/predict.py         candidates, labels, models, backtest, forecast
src/explain.py         bridge papers + Gemini cards
app/streamlit_app.py   Map · Emerging · Bridges · Next big things · Proof
```

## Limitations

- **Noisy tags.** Topics are machine-tagged. Modeling and Simulation absorbs the COVID-19 topics from 2020, so it's excluded from the rankings. Condensed Matter Physics is shrinking as its topics move into materials subfields, which makes its pairs look like they're rising; the forecast caps each subfield at two appearances.
- **Coverage growth.** Some growth reflects OpenAlex indexing more journals, for example business and marketing journals in 2022–24.
- **Overlap, not citations.** Recent papers haven't had time to collect citations, so links come from topic overlap.
- **Modest signal.** The backtest shows about 2.5 times chance in the top 100, but only 3 of the top 20. Growth in overlap is a signal, not proof of importance.
