"""Central configuration. Every tunable lives here and can be set from the
environment (backend/.env), so thresholds are measured values, not magic
numbers buried in the pipeline. Defaults reproduce the pre-refactor behaviour.

Run `python -m eval.calibrate_thresholds` to get data-driven suggestions for
CACHE_TOP_SCORE / CACHE_STRONG_SCORE / CALIB_BETA_*.
"""
import os

from dotenv import load_dotenv

# Load backend/.env before anything reads the environment.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _b(name: str, default: bool) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


# --- Embedding model (must be 384-d to fit the pgvector column) ------------
EMBED_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = 384

# --- Cache-first lookup -----------------------------------------------------
CACHE_TTL_HOURS = _i("CACHE_TTL_HOURS", 12)
CACHE_TOP_K = _i("CACHE_TOP_K", 30)
CACHE_TOP_SCORE = _f("CACHE_TOP_SCORE", 0.40)       # best hit must reach this
CACHE_STRONG_SCORE = _f("CACHE_STRONG_SCORE", 0.35)  # a hit counts as "strong" above this
# Complete answers for an exact repeat of a topic are reused for this long (0 = off).
ANSWER_CACHE_HOURS = _f("ANSWER_CACHE_HOURS", 6.0)

# --- Score calibration (sigmoid over raw cosine) ----------------------------
CALIB_ALPHA = _f("CALIB_ALPHA", 10.0)
CALIB_BETA_SHORT = _f("CALIB_BETA_SHORT", 0.30)  # queries of <= 2 words
CALIB_BETA_LONG = _f("CALIB_BETA_LONG", 0.35)
TITLE_BOOST = _f("TITLE_BOOST", 0.15)

# --- Retrieval --------------------------------------------------------------
ARXIV_CANDIDATES = _i("ARXIV_CANDIDATES", 50)
HYBRID_RETRIEVAL = _b("HYBRID_RETRIEVAL", True)  # BM25 + dense, fused with RRF
RRF_K = _i("RRF_K", 60)

# --- arXiv politeness (avoids HTTP 429) --------------------------------------
ARXIV_MIN_INTERVAL = _f("ARXIV_MIN_INTERVAL", 3.0)         # seconds between any two arXiv requests
ARXIV_CACHE_TTL_HOURS = _f("ARXIV_CACHE_TTL_HOURS", 6.0)   # reuse a topic's arXiv results
ARXIV_COOLDOWN_SECONDS = _f("ARXIV_COOLDOWN_SECONDS", 60.0)  # pause arXiv calls after a 429
ARXIV_HTTP_TIMEOUT = _f("ARXIV_HTTP_TIMEOUT", 20.0)     # seconds per arXiv HTTP request
ARXIV_LOCK_WAIT = _f("ARXIV_LOCK_WAIT", 45.0)           # max wait for the shared arXiv lock
SEARCH_RATE_LIMIT_PER_MIN = _i("SEARCH_RATE_LIMIT_PER_MIN", 10)  # per visitor; 0 turns it off
SEARCH_GLOBAL_LIMIT_PER_MIN = _i("SEARCH_GLOBAL_LIMIT_PER_MIN", 30)  # all visitors together; 0 turns it off

# --- Access ------------------------------------------------------------------
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://btp-sem-07.vercel.app"
).split(",") if o.strip()]
# This project's Vercel preview deployments (btp-sem-07-<hash>-<team>.vercel.app).
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", r"https://btp-sem-07(-[a-z0-9-]+)?\.vercel\.app")
EXPOSE_DOCS = _b("EXPOSE_DOCS", False)  # serve /docs, /openapi.json and /metrics to tunnel visitors too

# --- Graph ------------------------------------------------------------------
GRAPH_MAX_NODES = _i("GRAPH_MAX_NODES", 30)
