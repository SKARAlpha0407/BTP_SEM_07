from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StrictInt, field_validator
from typing import Any, Dict, List
import os
import math
import time

from . import config, graph, ratelimit, telemetry
from .arxiv_client import ArxivUnavailable, search_papers
from .embedding_service import (
    rank_with_cached_vectors,
    embed_batch,
    cosine_matrix,
    _MODEL_NAME as EMBED_MODEL,
)
from .grounding import grounding_report
from .hybrid import BM25, rrf_fuse, matched_terms
from .llm_service import (
    SYNTHESIS_UNAVAILABLE,
    is_placeholder_insight,
    extract_insights_batch,
    synthesize_results,
    get_cluster_labels,
    MODEL,
)
from .pipeline_cache import save_papers_and_embeddings, save_insights

def _calibrate_scores(papers, topic: str):
    """Map raw cosine onto a calibrated [0..1] score with additive keyword boosting.

    alpha/beta come from config.py; eval/calibrate_thresholds.py suggests values
    measured on the evaluation set.
    """
    alpha = config.CALIB_ALPHA
    is_short = len(topic.split()) <= 2
    beta = config.CALIB_BETA_SHORT if is_short else config.CALIB_BETA_LONG
    norm_topic = topic.strip().lower()

    for p in papers:
        raw = p.relevance_score or 0.0

        # Exact title match pin
        if raw >= 0.999:
            p.relevance_score = 1.0
            continue

        # Additive keyword boost (preserves relative ranking)
        norm_title = p.title.lower()
        if norm_topic in norm_title:
            raw = min(raw + config.TITLE_BOOST, 0.99)

        x = alpha * (raw - beta)
        x = max(-50.0, min(50.0, x))
        p.relevance_score = 1.0 / (1.0 + math.exp(-x))


def _hybrid_reorder(topic: str, papers: list, vectors: list):
    """Fuse the dense order with a BM25 order (RRF). Exact-title pins stay first."""
    if len(papers) < 3:
        return papers, vectors
    bm25 = BM25([f"{p.title} {p.abstract}" for p in papers])
    lex = bm25.scores(topic)
    lex_order = sorted(range(len(papers)), key=lambda i: -float(lex[i]))
    dense_order = list(range(len(papers)))  # papers arrive dense-ranked
    fused = rrf_fuse([dense_order, lex_order], k=config.RRF_K)
    # Fused score scaled to 0..1: 1.0 = first in both the dense and the BM25 ranking.
    k = config.RRF_K
    lex_rank = {i: r for r, i in enumerate(lex_order)}
    for i, p in enumerate(papers):
        p.fused_score = (1 / (k + 1 + i) + 1 / (k + 1 + lex_rank[i])) / (2 / (k + 1))
    pinned = [i for i in fused if (papers[i].relevance_score or 0) >= 0.999]
    rest = [i for i in fused if i not in set(pinned)]
    order = pinned + rest
    return [papers[i] for i in order], [vectors[i] for i in order]


if not os.environ.get("GROQ_API_KEY"):
    raise RuntimeError(
        "GROQ_API_KEY not set. Create backend/.env with "
        "GROQ_API_KEY=<your_key>. Refusing to start with a degraded LLM."
    )

app = FastAPI(title="Kavosh API")

# ---------------------------------------------------------------------------
# CORS: the local dev server and this project's Vercel deployments only.
# No cookies are used, so credentials are off. Override with CORS_ORIGINS
# (comma-separated) and CORS_ORIGIN_REGEX.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=config.CORS_ORIGIN_REGEX or None,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Developer pages: served to requests made on this machine, hidden from
# visitors who arrive through the tunnel (or set EXPOSE_DOCS=1).
_PRIVATE_PATHS = ("/docs", "/redoc", "/openapi.json", "/metrics")


@app.middleware("http")
async def private_pages_and_cache_control(request: Request, call_next):
    path = request.url.path
    if path.startswith(_PRIVATE_PATHS) and not config.EXPOSE_DOCS:
        peer = request.client.host if request.client else None
        if not ratelimit.is_loopback(peer) or ratelimit.is_proxied(request.headers):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
    response = await call_next(request)
    if not path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers["Cache-Control"] = "no-store"
    return response


class SearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    max_results: StrictInt = Field(default=5, ge=1, le=50)

    @field_validator("topic")
    @classmethod
    def topic_must_be_nonblank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("topic must be a non-empty string")
        if len(v) > 500:
            raise ValueError("topic must be 500 characters or fewer")
        return v


class PaperResponse(BaseModel):
    title: str
    abstract: str
    authors: List[str] = []
    arxiv_id: str
    arxiv_url: str
    pdf_url: str
    published: str
    categories: List[str] = []
    relevance_score: float | None = None
    summary: Dict[str, Any] | None = None
    matched_terms: List[str] = []

class GraphNode(BaseModel):
    id: int
    title: str
    val: float
    cluster: str | None = None
    year: int = 0
    short_label: str = ""
    primary_category: str = ""
    degree: int = 0
    author_surnames: List[str] = []
    arxiv_url: str = ""
    pdf_url: str = ""

class GraphLink(BaseModel):
    source: int
    target: int
    weight: float

class Graph(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]

class SearchResponse(BaseModel):
    papers: List[PaperResponse]
    synthesis: str
    graph: Graph
    meta: Dict[str, Any] = {}


@app.head("/health", include_in_schema=False)
@app.get("/health")
def health():
    db = "ok"
    try:
        from sqlalchemy import text as _text
        from .db.connection import SessionLocal
        with SessionLocal() as s:
            s.execute(_text("SELECT 1"))
    except Exception:
        db = "unavailable"
    return {"status": "ok", "db": db, "embed_model": EMBED_MODEL, "llm_model": MODEL,
            "hybrid_retrieval": config.HYBRID_RETRIEVAL}


@app.get("/metrics")
def metrics():
    """Latency percentiles, cache hit rate and LLM calls saved since startup."""
    return telemetry.snapshot()


def _stale_cached_papers(query_vec, limit: int) -> list:
    """Closest stored papers regardless of age, used when arXiv is unavailable."""
    if query_vec is None:
        return []
    try:
        from .db.connection import SessionLocal
        from .db.repository import search_similar_with_ttl
        from .pipeline_cache import load_paper_objects

        with SessionLocal() as s:
            rows = search_similar_with_ttl(
                s, query_vec, top_k=config.CACHE_TOP_K,
                max_age_hours=24 * 365, model_name=EMBED_MODEL,
            )
            rows = [(aid, sc) for aid, sc in rows if sc >= config.CACHE_STRONG_SCORE][:limit]
            if not rows:
                return []
            papers = load_paper_objects(s, [aid for aid, _ in rows])
            score_by_id = dict(rows)
            for p in papers:
                p.relevance_score = score_by_id.get(p.arxiv_id, 0.0)
            return papers
    except Exception:
        import logging
        logging.getLogger(__name__).exception("stale cache lookup failed")
        return []


def _topic_key(topic: str) -> str:
    return " ".join(topic.casefold().split())


# Every setting that changes the content or order of an answer. A saved answer is
# reused only when all of them match.
_ANSWER_SETTINGS = (
    "HYBRID_RETRIEVAL", "RRF_K", "DISPLAY_ORDER", "ARXIV_CANDIDATES", "CACHE_TTL_HOURS", "CACHE_TOP_K",
    "CACHE_TOP_SCORE", "CACHE_STRONG_SCORE", "CALIB_ALPHA", "CALIB_BETA_SHORT", "CALIB_BETA_LONG",
    "TITLE_BOOST", "GRAPH_MAX_NODES", "GRAPH_CLUSTERING",
)


def _config_key() -> str:
    import hashlib
    import json as _json

    settings = _json.dumps({k: getattr(config, k) for k in _ANSWER_SETTINGS}, sort_keys=True)
    return f"{EMBED_MODEL}|{MODEL}|{hashlib.sha1(settings.encode()).hexdigest()[:12]}"


def _load_saved_answer(topic: str, max_results: int):
    if config.ANSWER_CACHE_HOURS <= 0:
        return None
    try:
        from .db.connection import SessionLocal
        from .db.repository import get_saved_answer
        with SessionLocal() as s:
            return get_saved_answer(s, _topic_key(topic), max_results, _config_key(), config.ANSWER_CACHE_HOURS)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("saved-answer lookup failed")
        return None


def _save_answer(topic: str, max_results: int, response: dict) -> None:
    try:
        from fastapi.encoders import jsonable_encoder
        from .db.connection import SessionLocal
        from .db.repository import prune_answers, save_answer
        with SessionLocal() as s:
            save_answer(s, _topic_key(topic), max_results, _config_key(), jsonable_encoder(response))
            prune_answers(s, config.ANSWER_CACHE_HOURS, config.ANSWER_CACHE_MAX_ROWS)
            s.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("saved-answer write failed")


def _answer_is_complete(papers, synthesis: str) -> bool:
    """Only answers without failed parts are saved, so a failure is never frozen."""
    return bool(papers) and synthesis != SYNTHESIS_UNAVAILABLE and all(
        not is_placeholder_insight(p.summary) for p in papers
    )


class ErrorDetail(BaseModel):
    detail: str


_RETRY_AFTER = {"Retry-After": {"description": "Seconds to wait before retrying", "schema": {"type": "integer"}}}
SEARCH_RESPONSES = {
    404: {"model": ErrorDetail, "description": "arXiv returned no papers for the topic"},
    429: {"model": ErrorDetail, "description": "Too many searches from this visitor or in total", "headers": _RETRY_AFTER},
    500: {"model": ErrorDetail, "description": "Unexpected server error"},
    503: {"model": ErrorDetail, "description": "arXiv is unavailable and no stored papers match", "headers": _RETRY_AFTER},
}


@app.post("/search", response_model=SearchResponse, responses=SEARCH_RESPONSES)
def search(req: SearchRequest, request: Request):
    visitor = ratelimit.client_key(request.headers, request.client.host if request.client else None)
    allowed, retry_after = ratelimit.check(visitor, config.SEARCH_RATE_LIMIT_PER_MIN)
    if allowed:
        allowed, retry_after = ratelimit.check(ratelimit.GLOBAL_KEY, config.SEARCH_GLOBAL_LIMIT_PER_MIN)
    if not allowed:
        telemetry.incr("search_rate_limited")
        raise HTTPException(
            status_code=429,
            detail="Too many searches. Please wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )

    topic = req.topic.strip()
    t_start = time.perf_counter()
    telemetry.incr("search_total")
    cache_path = "cold"

    # The same topic searched recently: return the stored answer as it was,
    # with no arXiv or LLM calls.
    saved = _load_saved_answer(topic, req.max_results)
    if saved is not None:
        elapsed = time.perf_counter() - t_start
        telemetry.incr("answer_cache_hit")
        telemetry.observe("search_saved", elapsed)
        telemetry.observe("search_all", elapsed)
        saved.setdefault("meta", {})
        saved["meta"]["original_cache_path"] = saved["meta"].get("cache_path")
        saved["meta"]["cache_path"] = "saved"
        saved["meta"]["latency_seconds"] = round(elapsed, 3)
        return saved

    try:
        # Cache-first lookup
        from .db.connection import SessionLocal
        from .db.repository import (
            get_embeddings_for_ids,
            search_similar_with_ttl,
        )
        from .pipeline_cache import load_paper_objects
        from .embedding_service import embed_text

        try:
            query_vec = embed_text(topic).tolist()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("query embed failed")
            query_vec = None

        cache_hits: list = []
        if query_vec is not None:
            try:
                with SessionLocal() as _s:
                    rows = search_similar_with_ttl(
                        _s, query_vec, top_k=config.CACHE_TOP_K,
                        max_age_hours=config.CACHE_TTL_HOURS,
                        model_name=EMBED_MODEL,
                    )
                    top_score = rows[0][1] if rows else 0.0
                    strong = [(aid, sc) for aid, sc in rows if sc >= config.CACHE_STRONG_SCORE]
                    is_topic_query = len(topic.split()) <= 2
                    if is_topic_query and top_score >= config.CACHE_TOP_SCORE and len(strong) >= req.max_results:
                        ids = [aid for aid, _ in strong]
                        hydrated = load_paper_objects(_s, ids)
                        score_by_id = dict(strong)
                        for p in hydrated:
                            p.relevance_score = score_by_id.get(p.arxiv_id, 0.0)
                        cache_hits = hydrated
            except Exception:
                import logging
                logging.getLogger(__name__).exception("cache-first lookup failed")

        raw_papers: list = []
        if not cache_hits:
            try:
                with telemetry.timer("stage_arxiv"):
                    raw_papers = search_papers(topic, max_results=config.ARXIV_CANDIDATES)
            except ArxivUnavailable:
                telemetry.incr("arxiv_unavailable")
                # Enough stored papers for the whole reading map, not just the top list.
                cache_hits = _stale_cached_papers(query_vec, max(req.max_results, config.GRAPH_MAX_NODES))
                if not cache_hits:
                    raise HTTPException(
                        status_code=503,
                        detail="arXiv is busy right now. Please try again in a minute.",
                        headers={"Retry-After": "60"},
                    )
                cache_path = "stale"

        if cache_hits:
            if cache_path != "stale":
                cache_path = "warm"
                telemetry.incr("cache_hit")
            ranked_papers = cache_hits
            ranked_vectors = []
            top_papers = ranked_papers[: req.max_results]
            _calibrate_scores(top_papers, topic)
            top_papers.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
        else:
            # Fall back to arXiv when the cache is cold or weak
            if not raw_papers:
                raise HTTPException(
                    status_code=404,
                    detail=f"No papers matched topic {topic!r}",
                )

            # Semantic ranking
            cached_vecs: dict = {}
            try:
                with SessionLocal() as _s:
                    cached_vecs = get_embeddings_for_ids(
                        _s,
                        [p.arxiv_id for p in raw_papers],
                        EMBED_MODEL,
                    )
            except Exception:
                import logging
                logging.getLogger(__name__).exception("embedding cache read failed")

            with telemetry.timer("stage_rank"):
                ranked_papers, ranked_vectors = rank_with_cached_vectors(
                    topic, raw_papers, cached_vecs
                )
                if config.HYBRID_RETRIEVAL:
                    ranked_papers, ranked_vectors = _hybrid_reorder(
                        topic, ranked_papers, ranked_vectors
                    )
            top_papers = ranked_papers[: req.max_results]
            _calibrate_scores(top_papers, topic)
            # DISPLAY_ORDER=fused (default) keeps the RRF order and shows the fused
            # score; it ranked the query's own paper higher than re-sorting by the
            # dense score on short queries over the whole corpus
            # (eval/short_queries.py --pool full). DISPLAY_ORDER=score re-sorts by
            # the rescaled dense score instead.
            if config.HYBRID_RETRIEVAL and config.DISPLAY_ORDER == "fused":
                # Show the fused score, so the shown value follows the shown order.
                for p in top_papers:
                    if (p.relevance_score or 0) < 0.999 and getattr(p, "fused_score", None) is not None:
                        p.relevance_score = round(p.fused_score, 4)
            else:
                top_papers.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)

            try:
                save_papers_and_embeddings(ranked_papers, ranked_vectors, EMBED_MODEL)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("paper cache write failed")

        # Insights: cached first, then the LLM for the misses
        from .db.connection import SessionLocal
        from .db.repository import get_cached_insights

        cached: dict = {}
        try:
            with SessionLocal() as _s:
                cached = get_cached_insights(
                    _s,
                    [p.arxiv_id for p in top_papers],
                    MODEL,
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("insight cache read failed")

        # Placeholder rows ('Error' / 'N/A' everywhere) carry no content; refetch them.
        cached = {k: v for k, v in cached.items() if not is_placeholder_insight(v)}
        missing = [p for p in top_papers if p.arxiv_id not in cached]
        telemetry.incr("insights_requested", len(top_papers))
        telemetry.incr("insights_from_cache", len(top_papers) - len(missing))
        fresh: list = []
        if missing:
            telemetry.incr("llm_insight_calls")
            with telemetry.timer("stage_llm_insights"):
                fresh = extract_insights_batch(
                    [{"title": p.title, "abstract": p.abstract} for p in missing]
                )

        fresh_by_id = {
            missing[i].arxiv_id: fresh[i]
            for i in range(len(missing))
            if i < len(fresh)
        }
        for p in top_papers:
            if p.arxiv_id in cached:
                p.summary = cached[p.arxiv_id]
            elif p.arxiv_id in fresh_by_id:
                p.summary = fresh_by_id[p.arxiv_id]
            else:
                p.summary = None

        to_save = [(k, v) for k, v in fresh_by_id.items() if not is_placeholder_insight(v)]
        if to_save:
            try:
                save_insights(to_save, MODEL)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("insight cache write failed")

        # Flag insight terms that are not in the abstract
        for p in top_papers:
            if isinstance(p.summary, dict):
                p.summary = dict(p.summary)
                p.summary["grounding"] = grounding_report(p.summary, p.title, p.abstract)

        # Cross-paper synthesis
        with telemetry.timer("stage_llm_synthesis"):
            synthesis = synthesize_results(
                [{"title": p.title, "summary": p.summary} for p in top_papers]
            )

        # Reading map: nodes, links and clusters (backend/app/graph.py)
        graph_papers = ranked_papers[:min(config.GRAPH_MAX_NODES, len(ranked_papers))]
        nodes = graph.build_nodes(graph_papers)
        embs = embed_batch([p.abstract for p in graph_papers])
        links: List[Dict[str, Any]] = []
        if embs is not None:
            links = graph.build_links(graph_papers, nodes, cosine_matrix(embs, embs))
        clusters = graph.cluster(len(graph_papers), links, config.GRAPH_CLUSTERING)

        # Theme names from the LLM
        label_input = {
            cid: [graph_papers[idx].title for idx in indices]
            for cid, indices in clusters.items()
        }
        labels = get_cluster_labels(label_input, topic=topic)

        # Reverse map
        index_to_cluster: Dict[int, int] = {}
        for cid, indices in clusters.items():
            for idx in indices:
                index_to_cluster[idx] = cid

        # Every paper must belong to a cluster
        for i, node in enumerate(nodes):
            cid = index_to_cluster.get(i, i)
            label = labels.get(str(cid), labels.get(cid))
            if not (isinstance(label, str) and label.strip()):
                label = f"Cluster {cid}"
            node["cluster"] = label

        # Build the response with explicit field mapping
        papers_out = [
            PaperResponse(
                title=p.title,
                abstract=p.abstract,
                authors=p.authors,
                arxiv_id=p.arxiv_id,
                arxiv_url=p.arxiv_url,
                pdf_url=p.pdf_url,
                published=p.published,
                categories=p.categories,
                relevance_score=p.relevance_score,
                summary=p.summary,
                matched_terms=matched_terms(topic, p.title, p.abstract),
            )
            for p in top_papers
        ]

        elapsed = time.perf_counter() - t_start
        telemetry.observe(f"search_{cache_path}", elapsed)
        telemetry.observe("search_all", elapsed)
        response = {
            "papers": papers_out,
            "synthesis": synthesis,
            "graph": {"nodes": nodes, "links": links},
            "meta": {
                "cache_path": cache_path,
                "latency_seconds": round(elapsed, 3),
                "embed_model": EMBED_MODEL,
                "hybrid_retrieval": config.HYBRID_RETRIEVAL and cache_path == "cold",
            },
        }
        if cache_path in ("cold", "warm") and _answer_is_complete(top_papers, synthesis):
            _save_answer(topic, req.max_results, response)
        return response

    except HTTPException:
        telemetry.incr("search_http_error")
        raise
    except Exception:
        telemetry.incr("search_error")
        # Log the full traceback instead of returning a bare 500.
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="The search failed on the server. Please try again.")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
