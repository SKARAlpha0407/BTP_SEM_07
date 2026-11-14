from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List
import os
import math
import time

from . import config, telemetry
from .arxiv_client import search_papers
from .embedding_service import (
    rank_with_cached_vectors,
    embed_batch,
    cosine_matrix,
    _MODEL_NAME as EMBED_MODEL,
)
from .grounding import grounding_report
from .hybrid import BM25, rrf_fuse, matched_terms
from .llm_service import (
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
# CORS — allow the Next.js dev server (localhost:3000) to call this API.
# Both localhost and 127.0.0.1 variants are listed so neither origin gets
# blocked depending on how the browser resolves localhost.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cache_control(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers["Cache-Control"] = "no-store"
    return response


class SearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=50)

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


@app.get("/health")
def health():
    return {"status": "ok", "embed_model": EMBED_MODEL, "llm_model": MODEL,
            "hybrid_retrieval": config.HYBRID_RETRIEVAL}


@app.get("/metrics")
def metrics():
    """Latency percentiles, cache hit rate and LLM calls saved since startup."""
    return telemetry.snapshot()


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    topic = req.topic.strip()
    t_start = time.perf_counter()
    telemetry.incr("search_total")
    cache_path = "cold"

    try:
        # --- 1. Cache-first lookup ---
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

        if cache_hits:
            cache_path = "warm"
            telemetry.incr("cache_hit")
            ranked_papers = cache_hits
            ranked_vectors = []
            top_papers = ranked_papers[: req.max_results]
            _calibrate_scores(top_papers, topic)
        else:
            # --- 1b. Fallback: fetch from arxiv (cache cold or weak) ---
            with telemetry.timer("stage_arxiv"):
                raw_papers = search_papers(topic, max_results=config.ARXIV_CANDIDATES)
            if not raw_papers:
                raise HTTPException(
                    status_code=404,
                    detail=f"No papers matched topic {topic!r}",
                )

            # --- 2. Semantic ranking ---
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

            try:
                save_papers_and_embeddings(ranked_papers, ranked_vectors, EMBED_MODEL)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("paper cache write failed")

        # --- 3. Insights: cached first, then Groq for the misses ---
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

        if fresh_by_id:
            try:
                save_insights(list(fresh_by_id.items()), MODEL)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("insight cache write failed")

        # --- 3b. Grounding: flag insight terms that are not in the abstract ---
        for p in top_papers:
            if isinstance(p.summary, dict):
                p.summary = dict(p.summary)
                p.summary["grounding"] = grounding_report(p.summary, p.title, p.abstract)

        # --- 4. Cross-paper synthesis ---
        with telemetry.timer("stage_llm_synthesis"):
            synthesis = synthesize_results(
                [{"title": p.title, "summary": p.summary} for p in top_papers]
            )

        # --- 5. Graph nodes ---
        graph_papers = ranked_papers[:min(config.GRAPH_MAX_NODES, len(ranked_papers))]
        nodes: List[Dict[str, Any]] = []
        for i, p in enumerate(graph_papers):
            year_str = p.published[:4] if p.published and len(p.published) >= 4 else "0"
            try:
                year = int(year_str)
            except ValueError:
                year = 0
            
            first_author = p.authors[0].split()[-1] if p.authors else "Unknown"
            short_label = f"{first_author} {year}" if year > 0 else first_author
            cat = p.categories[0] if p.categories else ""
            auths = list({a.split()[-1] for a in (p.authors or []) if a.split()})[:5]
            
            nodes.append({
                "id": i,
                "title": p.title,
                "short_label": short_label,
                "year": year,
                "primary_category": cat,
                "author_surnames": auths,
                "val": p.relevance_score or 0,
                "degree": 0,
                "cluster": None
            })

        # --- 6. Graph links via combined similarity ---
        abstracts = [p.abstract for p in graph_papers]
        embs = embed_batch(abstracts)
        links: List[Dict[str, Any]] = []
        if embs is not None:
            sim_matrix = cosine_matrix(embs, embs)
            candidates = []
            for i in range(len(graph_papers)):
                for j in range(i + 1, len(graph_papers)):
                    sim = float(sim_matrix[i][j])
                    
                    cats_i = set(graph_papers[i].categories or [])
                    cats_j = set(graph_papers[j].categories or [])
                    cat_jac = len(cats_i & cats_j) / max(len(cats_i | cats_j), 1) if cats_i and cats_j else 0.0
                    
                    auth_i = set(nodes[i]["author_surnames"])
                    auth_j = set(nodes[j]["author_surnames"])
                    shared_auth = 1.0 if auth_i & auth_j else 0.0
                    
                    weight = 0.65 * sim + 0.25 * cat_jac + 0.10 * shared_auth
                    candidates.append((i, j, weight))

            candidates.sort(key=lambda x: x[2], reverse=True)
            threshold = 0.35 if len(candidates) < len(graph_papers) else 0.42
            max_edges = len(graph_papers) * 3
            
            for i, j, w in candidates:
                if w >= threshold and len(links) < max_edges:
                    links.append({"source": i, "target": j, "weight": w})
                    nodes[i]["degree"] += 1
                    nodes[j]["degree"] += 1

        max_deg = max((n["degree"] for n in nodes), default=1) or 1
        for n in nodes:
            n["val"] = 0.55 * (n["degree"] / max_deg) + 0.45 * n["val"]

        # --- 7. Connected-components clustering ---
        visited: set[int] = set()
        clusters: Dict[int, List[int]] = {}
        cluster_id = 0

        for i in range(len(graph_papers)):  # FIXED: uses graph_papers
            if i in visited:
                continue
            component: List[int] = []
            stack = [i]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for link in links:
                    if link["source"] == node:
                        stack.append(link["target"])
                    elif link["target"] == node:
                        stack.append(link["source"])
            clusters[cluster_id] = component
            cluster_id += 1

        # --- 8. Ask the LLM for theme names ---
        label_input = {
            cid: [graph_papers[idx].title for idx in indices]  # FIXED: uses graph_papers
            for cid, indices in clusters.items()
        }
        labels = get_cluster_labels(label_input, topic=topic)

        # --- 9. Reverse map ---
        index_to_cluster: Dict[int, int] = {}
        for cid, indices in clusters.items():
            for idx in indices:
                index_to_cluster[idx] = cid

        # --- 10. Final invariant ---
        for i, node in enumerate(nodes):
            cid = index_to_cluster.get(i, i)
            label = labels.get(str(cid), labels.get(cid))
            if not (isinstance(label, str) and label.strip()):
                label = f"Cluster {cid}"
            node["cluster"] = label

        # --- 11. Response ---
        # Explicit field mapping instead of PaperResponse(**p.__dict__) — this
        # is robust against future Paper field additions and against dataclass
        # repr helpers showing up in __dict__.
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
        return {
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

    except HTTPException:
        telemetry.incr("search_http_error")
        raise
    except Exception as e:
        telemetry.incr("search_error")
        # Surface the real traceback in Terminal 1 instead of a bare "500".
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all_route(full_path: str):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found", "path": f"/{full_path}"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
