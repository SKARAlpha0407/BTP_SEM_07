from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List
import os
from sentence_transformers import util

from .arxiv_client import search_papers
from .embedding_service import (
    rank_papers_with_vectors,
    rank_with_cached_vectors,
    embed_batch,
    _MODEL_NAME as EMBED_MODEL,
)
from .llm_service import (
    extract_insights_batch,
    synthesize_results,
    get_cluster_labels,
    MODEL,
)
from .pipeline_cache import save_papers_and_embeddings, save_insights

if not os.environ.get("GROQ_API_KEY"):
    raise RuntimeError(
        "GROQ_API_KEY not set. Create backend/.env with "
        "GROQ_API_KEY=<your_key>. Refusing to start with a degraded LLM."
    )

app = FastAPI(title="Research Copilot API")

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

class GraphNode(BaseModel):
    id: int
    title: str
    val: float
    cluster: str | None = None

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


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    topic = req.topic.strip()

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
                        _s, query_vec, top_k=30, max_age_hours=12,
                    )
                    top_score = rows[0][1] if rows else 0.0
                    strong = [(aid, sc) for aid, sc in rows if sc >= 0.35]
                    if top_score >= 0.4 and len(strong) >= req.max_results:
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
            ranked_papers = cache_hits
            ranked_vectors = []
            top_papers = ranked_papers[: req.max_results]
        else:
            # --- 1b. Fallback: fetch from arxiv (cache cold or weak) ---
            raw_papers = search_papers(topic, max_results=30)
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

            ranked_papers, ranked_vectors = rank_with_cached_vectors(
                topic, raw_papers, cached_vecs
            )
            top_papers = ranked_papers[: req.max_results]

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
        fresh: list = []
        if missing:
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

        # --- 4. Cross-paper synthesis ---
        synthesis = synthesize_results(
            [{"title": p.title, "summary": p.summary} for p in top_papers]
        )

        # --- 5. Graph nodes ---
        nodes: List[Dict[str, Any]] = [
            {"id": i, "title": p.title, "val": p.relevance_score or 0}
            for i, p in enumerate(top_papers)
        ]

        # --- 6. Graph links via pairwise cosine similarity ---
        abstracts = [p.abstract for p in top_papers]
        embs = embed_batch(abstracts)
        links: List[Dict[str, Any]] = []
        if embs is not None:
            sim_matrix = util.cos_sim(embs, embs)
            for i in range(len(top_papers)):
                for j in range(i + 1, len(top_papers)):
                    sim = float(sim_matrix[i][j])
                    if sim > 0.55:
                        links.append({"source": i, "target": j, "weight": sim})

        # --- 7. Connected-components clustering (store INDICES) ---
        visited: set[int] = set()
        clusters: Dict[int, List[int]] = {}
        cluster_id = 0

        for i in range(len(top_papers)):
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

        # --- 8. Ask the LLM for theme names, keyed by cluster id ---
        label_input = {
            cid: [top_papers[idx].title for idx in indices]
            for cid, indices in clusters.items()
        }
        labels = get_cluster_labels(label_input, topic=topic)

        # --- 9. Reverse map: node index -> cluster id ---
        index_to_cluster: Dict[int, int] = {}
        for cid, indices in clusters.items():
            for idx in indices:
                index_to_cluster[idx] = cid

        # --- 10. Final invariant: every node gets a non-empty cluster label ---
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
            )
            for p in top_papers
        ]

        return {
            "papers": papers_out,
            "synthesis": synthesis,
            "graph": {"nodes": nodes, "links": links},
        }

    except HTTPException:
        raise
    except Exception as e:
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