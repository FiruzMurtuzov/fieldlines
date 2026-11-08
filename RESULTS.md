# Fieldlines — Results log

Key numbers for the pitch, logged as the pipeline runs.

## Phase 0: API checks (2026-11-08 02:10 GMT)

- Taxonomy: **252 subfields**, 26 fields, 4 domains (Physical 89, Health 63, Social 58, Life 42). 250 have works in 2010–2024.
- Test co-occurrence call `filter=topics.subfield.id:1702,publication_year:2019-2021&group_by=topics.subfield.id` works: 769,575 AI works; top co-tags are Computer Vision (109,907), Information Systems (103,150), Control & Systems Eng. (55,723).
- **Cost per call:** a `group_by` or list call costs 1 credit = **$0.0001** (header `x-ratelimit-cost-usd`). A key gets $1/day (10,000 credits); keyless requests share $0.10/day per IP.
- **group_by is capped at 200 groups with no paging.** Workaround: merge both directions, c_ij = max(c_ij from i's call, c_ji from j's call). A pair is lost only if both subfields are large and the pair is outside both top-200 lists, which means a weak link between two big fields. Missing pairs are treated as 0 (+1 smoothing).
- Cursor paging needs a key; page-number paging works without one.
- Denominator N(p) = works with a primary topic (`primary_topic.id:!null`), about 94% of all works.

| Period | Years | All works | Topic-tagged works N(p) |
| --- | --- | --- | --- |
| P1 | 2010–12 | 24.1M | 23.0M |
| P2 | 2013–15 | 27.7M | 26.3M |
| P3 | 2016–18 | 29.6M | 27.8M |
| P4 | 2019–21 | 31.0M | 29.1M |
| P5 | 2022–24 | 31.3M | 29.4M |

**Projected Phase 1 cost:** 1 + 1 + 252 sizes + 252 × 5 co-occurrence = about 1,515 calls ≈ **$0.15**, well within one key's $1/day. No scope cut needed.
Spent so far: totals + sizes = $0.025, all from the keyless budget.

**Gemini:** key works. `models.list()` shows `gemini-3.8-flash` as the newest flash model; a JSON-mode test call returned valid JSON (first call took ~100 s, so Phase 5 will need timeouts and retries).

## Phase 1: Data pull (done, 02:25)

- Done (keyless budget, $0.0757 total): totals, subfield sizes (250 × 15 years), co-occurrence for **P4 and P5**. 334 of 504 calls hit the 200-group cap.
- Symmetry check: 43,268 pairs were seen from both sides; the two counts agree **exactly** (0% difference). Merged coverage is about 25.5k of 31,125 possible pairs per period.
- Spot check: AI × Molecular Biology 5,017 (P4) → 6,552 (P5).
- Rest pulled with a key: 522 live calls, $0.052. **Total Phase 1 spend: ~$0.13** (keyless $0.076 + key $0.052). The key still has $0.947 for today.
- 1,260 co-occurrence calls; 845 hit the 200-group cap. Pairs per period: P1 25,144 · P2 25,395 · P3 25,513 · P4 25,512 · P5 25,351.
- Symmetry: 108,263 pairs seen from both sides, max relative difference **0.0**.
- Spot check, AI × Molecular Biology: 4,062 → 4,209 → 4,515 → 5,017 → 6,552. AI × Biomedical Engineering: 2,317 → 9,128 (P1→P5).

### Data-quality fixes (02:25–02:33)

The first metrics run showed artefacts, so the whole pull was redone twice. Total spend is now about **$0.43**, with about $1.64 left today across 2 keys.

1. **Datasets:** Ecology jumped 241k → 535k works in 2024 alone, driven by 370k PlutoF biodiversity *dataset* records. Fixed with `type:article|review`.
2. **Zenodo spam:** "General Materials Science × Anthropology" went from 2 to 664 works in P5. All 664 were Indonesian SEO spam on Zenodo. "Business × Clinical Psychology" went 27 → 6,009, and 5,922 of those were Zenodo uploads. Fixed with `primary_location.source.type:journal`.
3. **COVID taxonomy quirk:** Modeling and Simulation tripled in 2020 because OpenAlex maps "COVID-19 epidemiological studies" into it. It stays on the map but is excluded from the rankings, candidates and labels (`config.ARTIFACT_SUBFIELDS`).

Final corpus is **journal articles and reviews**: P1 11.9M · P2 13.2M · P3 13.2M · P4 15.0M · P5 16.3M topic-tagged works. Symmetry is still exact (0.0 max difference). AI × Biomedical Engineering: 1,156 (P1) → 4,366 (P5).

## Phase 2: Metrics (done)

**Top emerging subfields** (acceleration = growth P4→P5 − growth P3→P4; n_P5 ≥ 2,000):

| Subfield | n P3 → P4 → P5 | Acceleration |
| --- | --- | --- |
| Business and International Management | 21k → 39k → 88k | +0.39 |
| Health Informatics | 10k → 21k → 53k | +0.34 |
| Computer Graphics and CAD | 34k → 37k → 50k | +0.28 |
| General Engineering | 6k → 8k → 12k | +0.17 |
| Software | 45k → 52k → 67k | +0.15 |
| Energy Engineering and Power Technology | 28k → 34k → 45k | +0.13 |

Caveat: Business growth is mostly the topic "SMEs and Digital Marketing" (7k → 73k), likely a coverage expansion of regional journals.

**Fastest-rising cross-field pairs** (Δ log AS P3→P5, already ≥ 20 papers in P3, ≥ 50 in P5):

| Pair | Papers P3 → P5 | Δ log AS |
| --- | --- | --- |
| Global and Planetary Change × Infectious Diseases | 25 → 286 | +1.91 |
| Information Systems × General Dentistry | 27 → 363 | +1.90 |
| Infectious Diseases × Sensory Systems (COVID smell loss) | 78 → 714 | +1.86 |
| Artificial Intelligence × Infectious Diseases | 50 → 901 | +1.80 |
| Aquatic Science × Electrical and Electronic Eng. | 155 → 1,041 | +1.80 |
| Oncology × Library and Information Sciences | 80 → 581 | +1.77 |
| Health Informatics × Education | 229 → 9,334 | +1.74 |
| Artificial Intelligence × Oral Surgery | 50 → 604 | +1.66 |

## Phase 3: Network, communities, bridges (done)

- Each period's graph has 250 nodes and about 4,100 edges (c ≥ 20, AS > 1). Louvain finds **6 communities** with modularity ≈ 0.50 in every period.
- P5 communities: biomedicine (77), social sciences and humanities (54), engineering and physical sciences (49), earth, environment and agriculture (29), CS and maths (23), health professions (18).
- **Top bridge subfields, P5** (participation and betweenness ranks): Statistics, Probability and Uncertainty · Medical Terminology · Chemical Health and Safety · Human-Computer Interaction · Acoustics and Ultrasonics · Complementary and Manual Therapy · Human Factors and Ergonomics · Anatomy.
- **Top rising cross-community pairs, P5:** Health Informatics × Education (Δ log AS +1.58, 9,334 papers) · Virology × Emergency Medical Services · Ocean Engineering × Statistical and Nonlinear Physics · Signal Processing × Transportation · Health Informatics × Library and Information Sciences.
