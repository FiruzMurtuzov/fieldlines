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

## Phase 1: Data pull (in progress)

- Done (keyless budget, $0.0757 total): totals, subfield sizes (250 × 15 years), co-occurrence for **P4 and P5**. 334 of 504 calls hit the 200-group cap.
- Symmetry check: 43,268 pairs were seen from both sides; the two counts agree **exactly** (0% difference). Merged coverage is about 25.5k of 31,125 possible pairs per period.
- Spot check: AI × Molecular Biology 5,017 (P4) → 6,552 (P5).
- Still to do: P1, P2 and most of P3 (~750 calls, ~$0.075). Blocked on an OpenAlex API key.
