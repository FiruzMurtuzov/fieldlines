"""Central configuration: years, periods, paths, thresholds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

HTTP_CACHE = RAW / "http_cache"          # requests-cache SQLite (".sqlite" appended)
BUDGET_LOG = RAW / "budget_log.csv"
RESULTS_MD = ROOT / "RESULTS.md"

OPENALEX_BASE = "https://api.openalex.org"

# Periods (3-year windows). 2025 is excluded because its counts are incomplete.
PERIODS = {
    "P0": (2007, 2009),   # features only (gives P1 momentum); never a label, not shown in the app
    "P1": (2010, 2012),
    "P2": (2013, 2015),
    "P3": (2016, 2018),
    "P4": (2019, 2021),
    "P5": (2022, 2024),
}
PERIOD_ORDER = list(PERIODS)
DISPLAY_PERIODS = ["P1", "P2", "P3", "P4", "P5"]
YEAR_MIN, YEAR_MAX = 2007, 2024

# HTTP behaviour
MAX_THREADS = 5
MAX_REQ_PER_SEC = 8.0
BACKOFF_SECONDS = [1, 2, 4, 8]   # 5 tries total

# Metrics
MIN_SUBFIELD_SIZE = 2000      # min papers in a period for a subfield to count as "established"
EMERGING_TOP_N = 20

# Graph
EDGE_MIN_COUNT = 20
EDGE_MIN_AS = 1.0
SEED = 42

# Prediction
LABEL_TOP_FRAC = 0.10
LABEL_MIN_COUNT = 50
FORECAST_TOP_N = 25
MAX_PER_SUBFIELD = 2     # diversity cap in the forecast list
CANDIDATE_MAX_AS = 1.0   # under-connected: fewer shared papers than sizes predict
CANDIDATE_MIN_C = 5      # ...but the link exists, so AS is not pure noise

# Peer-reviewed venues only. Without this, 2024 is flooded by datasets
# (370k PlutoF biodiversity records tagged Ecology) and Zenodo SEO spam
# (e.g. 5.9k "Business x Clinical Psychology" uploads) creates fake bridges.
# Conference papers are included because ~40% of AI/CS output is published there (NeurIPS, CVPR...).
# Repository uploads (arXiv, Zenodo) stay excluded: they carried the spam.
WORK_FILTER = ("type:article|review|conference-paper,"
               "primary_location.source.type:journal|conference|book series")

# Subfields whose series are distorted by taxonomy quirks. Kept on the map but
# excluded from rankings, labels and candidates.
ARTIFACT_SUBFIELDS = {
    2611: "Modeling and Simulation: absorbs the COVID-19 epidemiology topics from 2020 (3x jump in one year)",
}
