"""Derive the pipeline's thresholds from data instead of guessing them.

Each paper gives two queries: its full title (a long query) and the first two
content words of the title (a short query, <= 2 words). The positive for a
query is the paper's own abstract.

The semantic cache only serves short queries (main.py: <= 2 words), so the two
cache thresholds are measured on short queries. Short queries score far lower
than titles (median cosine ~0.3 vs ~0.65 for MiniLM), so values measured on
titles would stop the cache from ever firing. Negatives for the cache are
"off-topic" papers: those that share no arXiv category with the query's paper.
Same-topic neighbours are not counted as negatives, because a short topic query
is meant to match them.

  * CACHE_TOP_SCORE: the 95th percentile of the hardest off-topic cosine, so
    the best hit must beat what an off-topic paper reaches for 95% of queries.
  * CACHE_STRONG_SCORE: chosen by replaying main.py's cache rule (best hit >=
    CACHE_TOP_SCORE and at least --min-hits hits >= CACHE_STRONG_SCORE among
    the top --top-k): the lowest value at which at least --target-precision of
    the served hits are on-topic. Lower serves more queries from cache, higher
    serves fewer but cleaner; the full trade-off table is printed.
  * CALIB_BETA_SHORT / CALIB_BETA_LONG: midpoint between the positive and
    negative medians for short and long queries (display calibration).

Own-abstract versus hardest-negative (max F1) does not work for short queries:
the closest off-topic paper usually scores above the query's own paper, so F1
peaks at the bottom of the grid. On-topic is "shares an arXiv category", a
coarse label, so precisions are approximate.

    python -m eval.calibrate_thresholds --model all-MiniLM-L6-v2

Writes eval/results/thresholds.json and prints lines you can paste in .env.
"""
from __future__ import annotations

import argparse
import json
import os
import re

import numpy as np

from .data import load_corpus
from .systems import DenseSystem


def pos_neg(system: DenseSystem, queries):
    s = system.score(queries)
    idx = np.arange(len(queries))
    pos = s[idx, idx].copy()
    s[idx, idx] = -np.inf
    return pos, s.max(axis=1), s[np.isfinite(s)]


def short_query(title: str) -> str:
    """First two content words of a title, as a user's topic search would be."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]*", title) if len(w) > 3]
    return " ".join(words[:2]) or title


def same_topic(corpus) -> np.ndarray:
    """[i, j] is True when papers i and j share at least one arXiv category."""
    cats = [set(r.get("categories") or []) | {r.get("primary_category"), r.get("query_category")} - {None}
            for r in corpus]
    n = len(corpus)
    m = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(n):
            m[i, j] = bool(cats[i] & cats[j])
    return m


def replay_cache(s: np.ndarray, topic: np.ndarray, top: float, strong: float, top_k: int, min_hits: int):
    """Apply main.py's cache rule to every query's top_k scores."""
    order = np.argsort(-s, axis=1)[:, :top_k]
    served, on_topic, total = 0, 0, 0
    for i, row in enumerate(order):
        sc = s[i, row]
        hits = row[sc >= strong]
        if sc[0] >= top and len(hits) >= min_hits:
            served += 1
            on_topic += int(topic[i, hits].sum())
            total += len(hits)
    return served / len(s), (on_topic / total if total else float("nan"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="eval/results/thresholds.json")
    ap.add_argument("--top-k", type=int, default=30, help="CACHE_TOP_K in the server")
    ap.add_argument("--min-hits", type=int, default=5, help="default max_results of /search")
    ap.add_argument("--target-precision", type=float, default=0.70,
                    help="share of served cache hits that must be on-topic")
    args = ap.parse_args()

    corpus = load_corpus(args.corpus, args.limit)
    system = DenseSystem(args.model)
    system.index([r["abstract"] for r in corpus])

    long_q = [r["title"] for r in corpus]
    short_q = [short_query(r["title"]) for r in corpus]

    # Long queries: display calibration only.
    pos, _, all_neg = pos_neg(system, long_q)

    # Short queries: the cache thresholds.
    topic = same_topic(corpus)
    s = system.score(short_q)
    idx = np.arange(len(short_q))
    spos = s[idx, idx].copy()
    off = np.where(topic, -np.inf, s)          # off-topic scores only
    hard_off = off.max(axis=1)
    sneg = s.copy(); sneg[idx, idx] = -np.inf
    sall_neg = sneg[np.isfinite(sneg)]

    top = round(float(np.percentile(hard_off, 95)), 2)
    tradeoff = []
    for t in np.round(np.arange(0.20, top + 0.001, 0.01), 2):
        serve, precision = replay_cache(s, topic, top, float(t), args.top_k, args.min_hits)
        tradeoff.append({"strong": float(t), "served_fraction": round(serve, 4),
                         "served_hits_on_topic": round(precision, 4)})
    ok = [r for r in tradeoff if r["served_fraction"] > 0 and r["served_hits_on_topic"] >= args.target_precision]
    chosen = ok[0] if ok else tradeoff[-1]
    strong, serve, precision = chosen["strong"], chosen["served_fraction"], chosen["served_hits_on_topic"]

    out = {
        "model": args.model,
        "n": len(corpus),
        "short_query": {
            "example": short_q[0],
            "positive_cosine": {"p25": float(np.percentile(spos, 25)), "median": float(np.median(spos))},
            "hardest_off_topic_cosine": {"median": float(np.median(hard_off)),
                                         "p95": float(np.percentile(hard_off, 95))},
            "on_topic_base_rate": round(float(topic[~np.eye(len(corpus), dtype=bool)].mean()), 4),
            "cache_replay": {"top_k": args.top_k, "min_hits": args.min_hits,
                             "target_precision": args.target_precision,
                             "met": bool(ok),
                             "served_fraction": serve,
                             "served_hits_on_topic": precision},
            "tradeoff": tradeoff,
        },
        "long_query": {
            "positive_cosine": {"p25": float(np.percentile(pos, 25)), "median": float(np.median(pos))},
        },
        "suggested": {
            "CACHE_STRONG_SCORE": strong,
            "CACHE_TOP_SCORE": top,
            "CALIB_BETA_LONG": round(float((np.median(pos) + np.median(all_neg)) / 2), 2),
            "CALIB_BETA_SHORT": round(float((np.median(spos) + np.median(sall_neg)) / 2), 2),
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "short_query"} | {"short_query": {
        k: v for k, v in out["short_query"].items() if k != "tradeoff"}}, indent=2))
    print(f"\ncache trade-off at CACHE_TOP_SCORE={top} (short queries):")
    print("  strong  served  on-topic")
    for r in tradeoff[::2]:
        print(f"  {r['strong']:.2f}   {100 * r['served_fraction']:5.1f}%   {r['served_hits_on_topic']:.3f}")
    if not ok:
        print(f"\nWARNING: no threshold reaches {args.target_precision:.0%} on-topic; using the strictest.")
    print("\n# paste into backend/.env to adopt:")
    for key in ("CACHE_STRONG_SCORE", "CACHE_TOP_SCORE", "CALIB_BETA_LONG", "CALIB_BETA_SHORT"):
        print(f"{key}={out['suggested'][key]}")


if __name__ == "__main__":
    main()
