"""Semantic ranking for the live pipeline.

One ranking core (`_rank`) replaces three near-identical copies. The embedder
is chosen by EMBED_MODEL (see config.py / embedders.py) and must be 384-d to
fit the pgvector column. All vectors are L2-normalised numpy arrays.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import EMBED_MODEL
from .embedders import get_embedder

# Kept for backwards compatibility: main.py and the cache key on this name.
_MODEL_NAME = EMBED_MODEL


def _embedder():
    return get_embedder(_MODEL_NAME)


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def embed_text(text: str) -> np.ndarray:
    """Embed one string. Returns a 1-D normalised vector."""
    return _embedder().encode([text])[0]


def embed_batch(texts) -> Optional[np.ndarray]:
    """Embed a list of strings. Returns (n, dim) or None for an empty list."""
    if not texts:
        return None
    return _embedder().encode([t or "" for t in texts])


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between row sets (re-normalises defensively)."""
    from .embedders import l2_normalize

    return l2_normalize(a) @ l2_normalize(b).T


def _rank(
    query: str,
    papers: List,
    cached_vectors: Optional[Dict[str, List[float]]] = None,
) -> Tuple[list, List[List[float]]]:
    """Score papers by cosine(query, abstract); pin an exact title match first.

    Vectors found in `cached_vectors` (arxiv_id -> vector) are reused; only the
    remaining abstracts are encoded. Returns (ranked_papers, ranked_vectors).
    """
    if not papers:
        return [], []

    vec_map: Dict[str, List[float]] = dict(cached_vectors or {})
    todo = [p for p in papers if p.arxiv_id not in vec_map]
    if todo:
        new = embed_batch([p.abstract for p in todo])
        for p, v in zip(todo, new):
            vec_map[p.arxiv_id] = v.tolist()

    all_vecs = [vec_map[p.arxiv_id] for p in papers]
    scores = cosine_matrix(embed_text(query)[None, :], np.asarray(all_vecs, dtype=np.float32))[0]

    norm_query = _normalize(query)
    exact = []
    for p, s in zip(papers, scores):
        is_exact = _normalize(p.title) == norm_query
        p.relevance_score = 1.0 if is_exact else float(s)
        exact.append(is_exact)

    order = sorted(
        range(len(papers)),
        key=lambda i: (exact[i], papers[i].relevance_score or 0.0),
        reverse=True,
    )
    return [papers[i] for i in order], [list(all_vecs[i]) for i in order]


def rank_with_cached_vectors(
    query: str, papers: List, cached_vectors: dict
) -> Tuple[list, List[List[float]]]:
    return _rank(query, papers, cached_vectors)
