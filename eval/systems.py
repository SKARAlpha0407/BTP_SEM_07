"""Retrieval systems under test. Each maps (queries, corpus) -> score matrix.

Spec strings:
    <embedder spec>             dense retrieval, see backend/app/embedders.py
    bm25                        lexical baseline
    hybrid:<embedder spec>      BM25 + dense fused with Reciprocal Rank Fusion
"""
from __future__ import annotations

from typing import List

import numpy as np

from backend.app.embedders import get_embedder
from backend.app.hybrid import BM25


class System:
    name = "base"
    family = "unknown"

    def index(self, docs: List[str]) -> None:
        raise NotImplementedError

    def score(self, queries: List[str]) -> np.ndarray:
        raise NotImplementedError


class DenseSystem(System):
    def __init__(self, spec: str, batch_size: int = 64):
        self.emb = get_embedder(spec)
        self.name = spec
        self.family = self.emb.family
        self.batch_size = batch_size
        self.doc_vecs = None

    def _encode(self, texts: List[str], fn) -> np.ndarray:
        parts = [fn(texts[i:i + self.batch_size]) for i in range(0, len(texts), self.batch_size)]
        return np.vstack(parts)

    def index(self, docs):
        self.doc_vecs = self._encode(docs, self.emb.encode_documents)

    def score(self, queries):
        return self._encode(queries, self.emb.encode_queries) @ self.doc_vecs.T


class BM25System(System):
    name = "bm25"
    family = "lexical"

    def index(self, docs):
        self.bm25 = BM25(docs)

    def score(self, queries):
        return np.vstack([self.bm25.scores(q) for q in queries])


class CharTfidfSystem(System):
    """Character n-gram TF-IDF (3-5 grams within word boundaries), cosine.

    A lexical baseline that matches sub-word pieces, so misspellings still
    share most of their n-grams with the original word."""

    name = "char-tfidf"
    family = "lexical-subword"

    def index(self, docs):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.doc_m = self.vec.fit_transform(docs)

    def score(self, queries):
        q = self.vec.transform(queries)
        return (q @ self.doc_m.T).toarray()


class HybridSystem(System):
    family = "hybrid"

    def __init__(self, dense_spec: str, k: int = 60):
        self.dense = DenseSystem(dense_spec)
        self.lex = BM25System()
        self.name = f"hybrid:{dense_spec}"
        self.k = k

    def index(self, docs):
        self.dense.index(docs)
        self.lex.index(docs)

    @staticmethod
    def _rank_matrix(scores: np.ndarray) -> np.ndarray:
        order = np.argsort(-scores, axis=1, kind="stable")
        ranks = np.empty_like(order)
        rows = np.arange(scores.shape[0])[:, None]
        ranks[rows, order] = np.arange(scores.shape[1])[None, :]
        return ranks

    def score(self, queries):
        d = self.dense.score(queries)
        l = self.lex.score(queries)
        fused = 1.0 / (self.k + 1 + self._rank_matrix(d))
        # A document with zero lexical overlap gets no lexical vote.
        fused += np.where(l > 0, 1.0 / (self.k + 1 + self._rank_matrix(l)), 0.0)
        return fused


def build_system(spec: str) -> System:
    if spec == "bm25":
        return BM25System()
    if spec == "char-tfidf":
        return CharTfidfSystem()
    if spec.startswith("hybrid:"):
        return HybridSystem(spec.split(":", 1)[1])
    return DenseSystem(spec)
