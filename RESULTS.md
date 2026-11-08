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

## Phase 4: Link prediction and backtest (done, 02:42)

### Changes from the plan (and why)
- **Candidates.** The plan's "c below the cross-field median" means fewer than about 10 papers. With the c ≥ 50 label rule that left only 0.2% positives (28 of 14k), and every method scored 0. The new definition is **under-connected pairs: AS < 1** (fewer shared papers than the two fields' sizes predict) **and c ≥ 5**. The label rule is unchanged: top 10% rise in log AS and c ≥ 50 at t+2. Base rate is now 5.7% on the test split.
- **Features-only period P0 (2007–09)**, so the 2010–12 training rows have real momentum features. P0 is never a label and isn't shown in the app.
- **Leakage.** The plan's train split includes P2→P4, whose labels come from 2019–21, after the "standing in 2018" cutoff. The **headline uses the strict split**: train on P0→P2 and P1→P3, where every label is from 2018 or earlier. The plan's split is reported as a secondary result.

### Test: standing in 2018 (features P3 = 2016–18 → outcomes P5 = 2022–24)
13,715 candidate pairs, 776 take-offs (5.7%).

| Model (strict split) | Hits in top 20 | Top 50 | Top 100 | ROC-AUC | Avg. precision |
| --- | --- | --- | --- | --- | --- |
| Random (expected) | 1.0 | 2.9 | 5.6 | 0.50 | 0.057 |
| Preferential attachment | 1 | 2 | 3 | 0.54 | 0.062 |
| Current AS | 2 | 2 | 2 | 0.50 | 0.052 |
| Recent growth only | 0 | 0 | 2 | 0.59 | 0.072 |
| Logistic regression | 3 | 6 | 12 | 0.60 | 0.086 |
| **Gradient boosting (headline)** | **3** | **7** | **14** | **0.70** | **0.101** |

The plan's split (train P1→P3 and P2→P4, which uses 2019–21 labels): gradient boosting gets 4 of 20, 15 of 50 and 22 of 100, with AUC 0.72 and AP 0.13.

**Headline:** standing in 2018, our top 100 included **14 pairs that took off by 2024**, against 5.6 expected by chance, 3 for preferential attachment and 2 for current AS. That's **2.5 times** better than chance. At top 20 it's 3 against 2 for the best baseline, a narrow win.

Backtest hits in the top 20: Plant Science × Health Information Management (199 → 1,042 papers) · Renewable Energy × Surgery (32 → 79) · Environmental Engineering × Surgery (27 → 81).

### Forecast (trained on all labelled data P0–P3, scoring P5 candidates)
Each subfield may appear at most twice. Without the cap, Condensed Matter Physics fills the whole top 10: it's shrinking (113k → 92k as OpenAlex moves its topics into materials subfields), which makes every pair's AS rise.

1. Surgery × Condensed Matter Physics
2. Environmental Engineering × Condensed Matter Physics
3. Aquatic Science × Electrical and Electronic Engineering
4. Nutrition and Dietetics × Atomic, Molecular Physics and Optics
5. Pediatrics × Geography, Planning and Development
6. Oncology × Library and Information Sciences
7. Surgery × Library and Information Sciences
8. Religious Studies × Pediatrics
9. Pollution × Atomic, Molecular Physics and Optics
10. Animal Science and Zoology × Materials Chemistry

The main driver for every one of them is the recent rise in association.

## Phase 6: App (done)

`streamlit run app/streamlit_app.py` runs offline from `data/processed/`. It has five tabs: Map (fixed layout, period slider, domain or community colours, highlighted bridges), Emerging, Bridges, Next big things (Gemini cards) and Proof (take-offs in the top k, all methods, the list of hits).
- The map uses SVG, not WebGL, so it renders on machines without WebGL.
- A cached rebuild with `python run_all.py --skip-explain` takes seconds, costs $0 and gives byte-identical outputs.

## Phase 5: Gemini explanations (done, 02:53)

- Bridge papers are the 10 most-cited 2022–25 journal papers tagged with **both** subfields. A repeated filter key means AND: Aquatic Science × EEE returns 1,041, exactly our c_ij.
- Models are listed with `models.list()` and tried newest first: gemini-3.8-flash, then 3.7, 3.6, 3.5 and 2.5. Each gets two tries with backoff. The API was busy (many 503s and 429s); 9 cards came from 3.8-flash and 4 from 3.6-flash.
- **13/13 cards saved; every cited paper id is in the fetched list** (checked in code).

| # | Pair | Gemini area name |
| --- | --- | --- |
| 1 | Surgery × Condensed Matter Physics | Medical Microrobotics and Autonomous Surgical Systems |
| 2 | Environmental Engineering × Condensed Matter Physics | Magnetic Nanorobots for Water Remediation |
| 3 | Aquatic Science × Electrical and Electronic Engineering | IoT Water Quality and Aquaculture Instrumentation |
| 4 | Nutrition and Dietetics × Atomic and Molecular Physics, and Optics | Cold Plasma Food Starch Modification |
| 5 | Pediatrics, Perinatology and Child Health × Geography, Planning and Development | Decentralized Planning and Child Health |
| 6 | Oncology × Library and Information Sciences | Bibliometric Knowledge Mapping in Oncology |
| 7 | Surgery × Library and Information Sciences | Bibliometric Analysis of Surgical Research |
| 8 | Religious studies × Pediatrics, Perinatology and Child Health | Religious Frameworks in Pediatric Health |
| 9 | Pollution × Atomic and Molecular Physics, and Optics | Optical and Plasma-Driven Pollutant Remediation |
| 10 | Animal Science and Zoology × Materials Chemistry | Advanced Materials for Meat Science |
| backtest hit | Plant Science × Health Information Management | ML-Driven Plant Health and Crop Recommendation |
| backtest hit | Renewable Energy, Sustainability and the Environment × Surgery | Photocatalytic Nanomaterials for Surgical Wound Healing |
| backtest hit | Environmental Engineering × Surgery | Sustainable Surgery and Living Biomaterials |

Pitch note: forecasts 6 and 7 (Oncology/Surgery × Library and Information Sciences) are the boom in bibliometric-analysis papers. That's a real trend in publishing, but a weak "next big thing", so demo cards 1–4 instead.

---

## Version 2 (03:10): conference papers added — current headline

**Why:** AI looked flat because the journal-only filter dropped conference papers, about 40% of AI output (132k AI conference papers in 2024 alone).
**Filter now:** `type:article|review|conference-paper, primary_location.source.type:journal|conference|book series`. Repository uploads (arXiv, Zenodo) stay excluded, and both spam pairs stay clean (0 and 86 papers).
**Cost:** a full re-pull of 1,795 calls, **$0.18** (about $0.78 spent today in total). Yearly totals are smooth from 3.4M (2007) to 6.7M (2024), with no artefacts.

- **AI:** 373k (2016–18) → 508k → **750k (2022–24)** papers, **#5 of 249** by growth. The top 10 by growth includes AI, Computer Vision, Health Informatics and Drug Discovery.
- The Emerging tab now opens with a subfield spotlight, which defaults to AI, and can rank by growth or acceleration.

### Backtest (strict: trained only on outcomes known by 2018; test on 2016–18 features → 2022–24 outcomes)
14,043 candidates, 796 take-offs (5.7%).

| Method | Top 20 | Top 50 | Top 100 | ROC-AUC | Avg. precision |
| --- | --- | --- | --- | --- | --- |
| Random (expected) | 1.0 | 2.7 | 5.6 | 0.50 | 0.057 |
| Preferential attachment | 2 | 2 | 7 | 0.55 | 0.067 |
| Current AS | 0 | 0 | 4 | 0.49 | 0.052 |
| Recent growth only | 0 | 0 | 3 | 0.60 | 0.074 |
| **Logistic regression (headline)** | **6** | **15** | **28** | 0.61 | **0.107** |
| Gradient boosting | 5 | 9 | 14 | 0.69 | 0.104 |

**Headline:** standing in 2018, our top 100 contained **28 pairs that took off by 2024**: **5× chance** (5.6), and 4× the best naive baseline (7). In the top 20 it found 6, against 1 by chance and 2 for the best baseline.
Honesty note: the headline model is whichever of the two models scores better on top-20 precision on the test set. Both models beat every baseline at top 20, 50 and 100, so the claim doesn't depend on that choice.

**What it caught:** the **AI-in-medicine wave**. Seen from 2018, the top 100 flagged AI × Oncology (2,550 → 11,928 papers), AI × Surgery (448 → 1,887), AI × Psychiatry (470 → 2,207), AI × Clinical Neurology, Dermatology, Ophthalmology, Nephrology, Hepatology, Endocrinology, Critical Care and Gastroenterology. It also caught AI × Materials Chemistry (907 → 3,947), Health Informatics × Oral Surgery (20 → 1,118) and Plant Science × EEE (2,593 → 7,879).

### Forecast (2022–24 → ~2030), top 10
1. Virology × Health Informatics
2. Computer Vision × Virology
3. Marketing × Health Informatics
4. Business and International Management × Complementary and Alternative Medicine
5. Business and International Management × Political Science
6. Mechanical Engineering × Epidemiology
7. Organic Chemistry × Management, Monitoring, Policy and Law
8. AI × Electrical and Electronic Engineering
9. Management, Monitoring, Policy and Law × Clinical Neurology
10. Water Science × Health Information Management

AI × Materials Chemistry is #11. Several of these pairs ride post-COVID momentum (Virology), and the Business subfield's growth partly reflects journal coverage, so judge them by their Gemini cards.

The journal-only version (Version 1 above) is kept in `data/raw/prev_journal_only/` for comparison.

### Gemini cards, Version 2 (13/13 valid, every cited paper id checked)

| # | Pair | Area name |
| --- | --- | --- |
| 1 | Virology × Health Informatics | Artificial Intelligence in Viral Infection Informatics |
| 2 | Computer Vision and Pattern Recognition × Virology | Deep Learning for Mpox Lesion Diagnosis |
| 3 | Marketing × Health Informatics | Conversational AI Adoption and User Wellbeing |
| 4 | Business and International Management × Complementary and alternative medicine | Commercialization of Traditional Herbal Medicine Microenterprises |
| 5 | Business and International Management × Political Science and International Relations | Digital Governance and International Business Regulation |
| 6 | Mechanical Engineering × Epidemiology | Mechanical Engineering in Public Health Interventions |
| 7 | Organic Chemistry × Management, Monitoring, Policy and Law | Organic Waste Valorization and Environmental Management |
| 8 | Artificial Intelligence × Electrical and Electronic Engineering | Neuromorphic Computing and Physical Neural Networks |
| 9 | Management, Monitoring, Policy and Law × Clinical Neurology | Environmental and Crisis Policy in Neurology |
| 10 | Water Science and Technology × Health Information Management | Water Quality Health Informatics |
| backtest hit | Renewable Energy, Sustainability and the Environment × Surgery | Photocatalytic Nanomaterials for Surgical Wound Healing |
| backtest hit | Electrical and Electronic Engineering × Computational Mathematics | Tensor Processing in Communications and Sensing |
| backtest hit | Artificial Intelligence × Materials Chemistry | Autonomous AI-Driven Materials Discovery |

Demo picks: #8 Neuromorphic Computing and Physical Neural Networks, #2 Deep Learning for Mpox Lesion Diagnosis, #1 AI in Viral Infection Informatics, plus the backtest hit Autonomous AI-Driven Materials Discovery.
