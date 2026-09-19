
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import asyncio

from .arxiv_client import search_papers, Paper
from .embedding_service import rank_papers, embed_text
from .llm_service import extract_insights_batch, synthesize_results, get_cluster_labels
from sentence_transformers import util
import numpy as np

app = FastAPI(title="Research Copilot API")

# CORS at the top
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=50)

    @field_validator("topic")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("topic must not be blank")
        return v

class PaperResponse(BaseModel):
    title: str
    authors: List[str]
    abstract: str
    arxiv_id: str
    arxiv_url: str
    pdf_url: str
    published: str
    categories: List[str]
    relevance_score: Optional[float]
    summary: Optional[Dict[str, Any]]

@app.post("/search", response_model=Dict[str, Any])
def search(req: SearchRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic must not be blank")

    try:
        raw_papers = search_papers(topic, max_results=30)
        if not raw_papers:
            return {"papers": [], "synthesis": "No papers found.", "graph": {"nodes": [], "links": []}}

        ranked_papers = rank_papers(topic, raw_papers)
        top_papers = ranked_papers[:req.max_results]

        # Batch Extract Insights (Groq)
        insights = extract_insights_batch([{"title": p.title, "abstract": p.abstract} for p in top_papers])
        for i, p in enumerate(top_papers):
            p.summary = insights[i] if i < len(insights) else None

        # Synthesis
        synthesis = synthesize_results([{"title": p.title, "summary": p.summary} for p in top_papers])

        # Graph Construction
        nodes = []
        for i, p in enumerate(top_papers):
            nodes.append({"id": i, "title": p.title, "val": p.relevance_score or 0})

        links = []
        abstracts = [p.abstract for p in top_papers]
        from .embedding_service import model
        embs = model.encode(abstracts, convert_to_tensor=True)
        sim_matrix = util.cos_sim(embs, embs)

        for i in range(len(top_papers)):
            for j in range(i + 1, len(top_papers)):
                sim = float(sim_matrix[i][j])
                if sim > 0.7:
                    links.append({"source": i, "target": j, "weight": sim})

        # Cluster Labeling
        visited = set()
        clusters = {}
        cluster_id = 0
        
        for i in range(len(top_papers)):
            if i not in visited:
                component = []
                stack = [i]
                while stack:
                    node = stack.pop()
                    if node not in visited:
                        visited.add(node)
                        component.append(node)
                        for link in links:
                            if link['source'] == node: stack.append(link['target'])
                            elif link['target'] == node: stack.append(link['source'])
                
                clusters[cluster_id] = [top_papers[idx].title for idx in component]
                cluster_id += 1
        
        labels = get_cluster_labels(clusters)
        
        # Final Invariant Guard
        for i, node in enumerate(nodes):
            cid = clusters.get(i, i) # Simplified, use first cluster it belongs to
            # Since we built clusters map: clusters[cluster_id] = [indices]
            # We need the reverse: index -> cluster_id
            pass

        # Correcting reverse mapping
        index_to_cluster = {}
        for cid, indices in clusters.items():
            for idx in indices:
                index_to_cluster[idx] = cid
        
        for i, node in enumerate(nodes):
            cid = index_to_cluster.get(i, i)
            node["cluster"] = labels.get(str(cid), labels.get(cid, f"Cluster {cid}"))
            if not (isinstance(node["cluster"], str) and node["cluster"].strip()):
                node["cluster"] = f"Cluster {cid}"

        return {
            "papers": [PaperResponse(**p.__dict__) for p in top_papers],
            "synthesis": synthesis,
            "graph": {"nodes": nodes, "links": links}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
