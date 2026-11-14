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

# --- Score calibration (sigmoid over raw cosine) ----------------------------
CALIB_ALPHA = _f("CALIB_ALPHA", 10.0)
CALIB_BETA_SHORT = _f("CALIB_BETA_SHORT", 0.30)  # queries of <= 2 words
CALIB_BETA_LONG = _f("CALIB_BETA_LONG", 0.35)
TITLE_BOOST = _f("TITLE_BOOST", 0.15)

# --- Retrieval --------------------------------------------------------------
ARXIV_CANDIDATES = _i("ARXIV_CANDIDATES", 50)
HYBRID_RETRIEVAL = _b("HYBRID_RETRIEVAL", False)  # BM25 + dense, fused with RRF
RRF_K = _i("RRF_K", 60)

# --- Graph ------------------------------------------------------------------
GRAPH_MAX_NODES = _i("GRAPH_MAX_NODES", 30)

# --- Access control -------------------------------------------------------
# Origins allowed to call the API from a browser: local dev plus the deployed
# site and its own preview deployments, not every *.vercel.app site.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://btp-sem-07.vercel.app",
).split(",") if o.strip()]
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"https://btp-sem-07(-[a-z0-9-]+)?\.vercel\.app")
# Searches per client per minute (each one can cost several LLM calls).
SEARCH_RATE_LIMIT = _i("SEARCH_RATE_LIMIT", 12)
