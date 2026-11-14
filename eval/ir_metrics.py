"""Ranking metrics for known-item retrieval (one relevant document per query)."""
from __future__ import annotations

import math
from typing import Dict, Sequence

import numpy as np


def ranks_of_targets(scores: np.ndarray, targets: Sequence[int]) -> np.ndarray:
    """1-based rank of each query's target document. scores: (n_queries, n_docs).

    Ties are broken pessimistically (the target is placed after equal scores),
    so a model that scores everything identically gets no credit.
    """
    t = np.asarray(targets)
    target_scores = scores[np.arange(len(t)), t][:, None]
    better = (scores > target_scores).sum(axis=1)
    ties = (scores == target_scores).sum(axis=1) - 1
    return better + ties + 1


def summarize(ranks: np.ndarray, k: int = 10) -> Dict[str, float]:
    ranks = np.asarray(ranks, dtype=np.float64)
    hit = ranks <= k
    return {
        "recall@1": float((ranks <= 1).mean()),
        f"recall@{k}": float(hit.mean()),
        "mrr": float((1.0 / ranks).mean()),
        f"ndcg@{k}": float(np.where(hit, 1.0 / np.log2(ranks + 1), 0.0).mean()),
    }


def mean_ci95(values: Sequence[float]) -> tuple:
    """Mean and half-width of a normal-approximation 95% interval across seeds."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2:
        return float(v.mean()), 0.0
    return float(v.mean()), float(1.96 * v.std(ddof=1) / math.sqrt(len(v)))
