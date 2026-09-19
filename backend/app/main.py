from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List
from sentence_transformers import util

from .arxiv_client import search_papers
from .embedding_service import rank_papers, embed_batch
from .llm_service import (
    extract_insights_batch,
    synthesize_results,
    get_cluster_labels,
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


@app.post("/search", response_model=Dict[str, Any])
def search(req: SearchRequest):
    topic = req.topic.strip()

    try:
        # --- 1. Fetch from arxiv ---
        raw_papers = search_papers(topic, max_results=30)
        if not raw_papers:
            raise HTTPException(
                status_code=404,
                detail=f"No papers matched topic {topic!r}",
            )

        # --- 2. Semantic ranking ---
        ranked_papers = rank_papers(topic, raw_papers)
        top_papers = ranked_papers[: req.max_results]

        # --- 3. Batch extract insights (single Groq call) ---
        insights = extract_insights_batch(
            [{"title": p.title, "abstract": p.abstract} for p in top_papers]
        )
        for i, p in enumerate(top_papers):
            p.summary = insights[i] if i < len(insights) else None

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
                    if sim > 0.7:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)