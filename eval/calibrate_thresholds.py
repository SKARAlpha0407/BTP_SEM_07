"""Derive the pipeline's thresholds from data instead of guessing them.

For each query (a paper title) it compares the cosine to its own abstract
(positive) with the cosines to all other abstracts (negatives), then reports:

  * the cosine threshold that best separates positives from the hardest
    negative (max F1)            -> candidate for CACHE_STRONG_SCORE
  * the 25th percentile of positive scores -> candidate for CACHE_TOP_SCORE
  * the midpoint between the positive and negative medians, separately for
    short (<= 2 words) and longer queries -> candidates for CALIB_BETA_*

    python -m eval.calibrate_thresholds --model all-MiniLM-L6-v2

Writes eval/results/thresholds.json and prints lines you can paste in .env.
Titles are long queries, so short-query betas are estimated from the first two
content words of each title; treat those as approximate.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

from .data import load_corpus
from .systems import DenseSystem


def best_f1_threshold(pos: np.ndarray, neg: np.ndarray):
    best = (0.0, 0.0)
    for t in np.linspace(0.05, 0.95, 91):
        tp = (pos >= t).sum()
        fp = (neg >= t).sum()
        fn = (pos < t).sum()
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best[1]:
            best = (float(t), float(f1))
    return best


def pos_neg(system: DenseSystem, queries):
    s = system.score(queries)
    idx = np.arange(len(queries))
    pos = s[idx, idx].copy()
    s[idx, idx] = -np.inf
    return pos, s.max(axis=1), s[np.isfinite(s)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="eval/results/thresholds.json")
    args = ap.parse_args()

    corpus = load_corpus(args.corpus, args.limit)
    system = DenseSystem(args.model)
    system.index([r["abstract"] for r in corpus])

    long_q = [r["title"] for r in corpus]
    short_q = [" ".join([w for w in r["title"].split() if len(w) > 3][:2]) or r["title"]
               for r in corpus]

    pos, hard_neg, all_neg = pos_neg(system, long_q)
    spos, _, sall_neg = pos_neg(system, short_q)
    thr, f1 = best_f1_threshold(pos, hard_neg)

    out = {
        "model": args.model,
        "n": len(corpus),
        "positive_cosine": {"p05": float(np.percentile(pos, 5)), "p25": float(np.percentile(pos, 25)),
                            "median": float(np.median(pos))},
        "hardest_negative_cosine": {"median": float(np.median(hard_neg)),
                                    "p95": float(np.percentile(hard_neg, 95))},
        "suggested": {
            "CACHE_STRONG_SCORE": round(thr, 2),
            "CACHE_STRONG_SCORE_f1": round(f1, 4),
            "CACHE_TOP_SCORE": round(float(np.percentile(pos, 25)), 2),
            "CALIB_BETA_LONG": round(float((np.median(pos) + np.median(all_neg)) / 2), 2),
            "CALIB_BETA_SHORT": round(float((np.median(spos) + np.median(sall_neg)) / 2), 2),
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))
    print("\n# paste into backend/.env to adopt:")
    for key in ("CACHE_STRONG_SCORE", "CACHE_TOP_SCORE", "CALIB_BETA_LONG", "CALIB_BETA_SHORT"):
        print(f"{key}={out['suggested'][key]}")


if __name__ == "__main__":
    main()
