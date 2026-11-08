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
    "P1": (2010, 2012),
    "P2": (2013, 2015),
    "P3": (2016, 2018),
    "P4": (2019, 2021),
    "P5": (2022, 2024),
}
PERIOD_ORDER = list(PERIODS)
YEAR_MIN, YEAR_MAX = 2010, 2024

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
