"""Lexical retrieval (BM25) and rank fusion (RRF).

Hybrid = dense + lexical. Dense models fail on rare jargon and typos in
different ways than exact term matching does, so fusing both rankings is the
standard production answer to the Sem-6 finding that no single representation
is robust everywhere.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Sequence

import numpy as np

from .embedders import tokenize


class BM25:
    """Okapi BM25 over a fixed document list."""

    def __init__(self, docs: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_tfs: List[Counter] = [Counter(tokenize(d)) for d in docs]
        self.doc_len = np.array([sum(tf.values()) for tf in self.doc_tfs], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if len(self.doc_len) else 0.0
        n = len(self.doc_tfs)
        df: Counter = Counter()
        for tf in self.doc_tfs:
            df.update(tf.keys())
        self.idf: Dict[str, float] = {
            t: math.log(1.0 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }
        self.postings: Dict[str, List[tuple]] = {}
        for i, tf in enumerate(self.doc_tfs):
            for t, c in tf.items():
                self.postings.setdefault(t, []).append((i, c))

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(len(self.doc_tfs), dtype=np.float32)
        if not self.avgdl:
            return out
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, c in self.postings[term]:
                denom = c + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * c * (self.k1 + 1) / denom
        return out


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = 60) -> List[int]:
    """Reciprocal Rank Fusion. Each ranking is a list of item ids, best first."""
    score: Dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score, key=lambda i: (-score[i], i))


def matched_terms(query: str, title: str, abstract: str, limit: int = 8) -> List[str]:
    """Query terms that literally occur in the paper: a cheap 'why this ranked'."""
    doc = set(tokenize(title)) | set(tokenize(abstract))
    seen, out = set(), []
    for t in tokenize(query):
        if len(t) > 2 and t in doc and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:limit]
