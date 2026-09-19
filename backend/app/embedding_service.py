from sentence_transformers import SentenceTransformer, util
import numpy as np
import threading
from typing import List

# ---------------------------------------------------------------------------
# Model loading — lazy, thread-safe, CPU-only.
#
# Why CPU: on Apple Silicon, sentence-transformers defaults to the MPS (Metal)
# GPU backend. When Uvicorn runs two /search handlers concurrently (its
# threadpool), both threads encode into the same MTLCommandBuffer and macOS
# aborts the process with:
#     failed assertion _status < MTLCommandBufferStatusCommitted
# This is a C++-level abort — Python cannot catch it, and the whole server
# dies. Forcing CPU sidesteps MPS entirely. MiniLM on CPU is ~50-150ms per
# batch of 5; the GPU was never the bottleneck here.
# ---------------------------------------------------------------------------

_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    """Lazy, thread-safe singleton. Loads MiniLM on CPU exactly once."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(_MODEL_NAME, device="cpu")
    return _model


def embed_text(text: str):
    """Embed a single string. Returns a torch tensor on CPU."""
    model = _get_model()
    with _model_lock:
        return model.encode(text, convert_to_tensor=True)


def rank_papers(query: str, papers: List):
    """
    Rank papers by cosine similarity between the query and each abstract.
    Thread-safe: serializes the encode call so concurrent /search requests
    cannot race inside the model.
    """
    if not papers:
        return []

    model = _get_model()

    query_emb = model.encode(query, convert_to_tensor=True)
    abstracts = [p.abstract for p in papers]

    # Serialize the batch encode — the only place a race could occur.
    with _model_lock:
        paper_embs = model.encode(abstracts, convert_to_tensor=True)

    # util.cos_sim is pure math on CPU tensors — safe to run outside the lock.
    scores = util.cos_sim(query_emb, paper_embs)[0]

    for i, paper in enumerate(papers):
        paper.relevance_score = float(scores[i])

    return sorted(papers, key=lambda x: x.relevance_score or 0, reverse=True)

def embed_batch(texts):
    """
    Public batch-embedding helper. Thread-safe, CPU-only, returns a CPU tensor.
    Use this from main.py instead of reaching into the internal _model.
    """
    if not texts:
        return None
    model = _get_model()
    with _model_lock:
        return model.encode(texts, convert_to_tensor=True)