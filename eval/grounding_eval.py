"""How well does the lexical grounding check catch invented terms?

For N corpus papers a faithful four-field summary is built from the paper's own
abstract (sentences 1, 2, 3 and the last as tldr/problem/methods/benchmarks).
A corrupted copy then gets K foreign terms: words of length >= 6 taken from
other papers' abstracts that do not occur in this paper's title or abstract
(stand-ins for an invented method or dataset name), appended to the methods
and benchmarks fields.

Measured with backend/app/grounding.py exactly as the app uses it:
  - injected-term recall: share of injected terms listed as unsupported;
  - false flags: share of faithful summaries with any unsupported term;
  - score separation: grounding score of faithful vs corrupted summaries,
    ROC AUC, and how often each falls under the app's 50% "weak" line.

Limitations: faithful summaries here copy the abstract's words, so the false-
flag rate is a lower bound (a real LLM paraphrases); the injected words are
real English words from other abstracts, not made-up names.

    python -m eval.grounding_eval
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys

import numpy as np

from backend.app.embedders import tokenize
from backend.app.grounding import grounding_report

from .data import load_corpus

OUT = "eval/results/embedding_study/grounding"


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def live_scores():
    """Grounding scores of the real LLM summaries stored by the app (read-only)."""
    from sqlalchemy import text

    from backend.app.db.connection import SessionLocal

    with SessionLocal() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = s.execute(text(
            "SELECT p.title, p.abstract, i.tldr, i.problem, i.methods, i.benchmarks "
            "FROM paper_insights i JOIN papers p USING (arxiv_id)")).fetchall()
        s.rollback()
    scores, flagged = [], 0
    for t, a, *fields in rows:
        rep = grounding_report(dict(zip(("tldr", "problem", "methods", "benchmarks"), fields)), t, a)
        if rep["score"] is not None:
            scores.append(rep["score"])
            flagged += bool(rep["unsupported"])
    v = np.asarray(scores)
    return {"n": len(v), "mean_score": float(v.mean()), "median_score": float(np.median(v)),
            "p10_score": float(np.percentile(v, 10)), "share_weak_below_50pct": float((v < 0.5).mean()),
            "share_with_any_flag": flagged / len(v)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--k", nargs="+", type=int, default=[1, 2, 3, 5])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--db", action="store_true", help="also score the LLM summaries stored in the local database")
    args = ap.parse_args()
    from sklearn.metrics import roc_auc_score

    rng = random.Random(args.seed)
    corpus = [r for r in load_corpus(args.corpus) if len(sentences(r["abstract"])) >= 4]
    papers = rng.sample(corpus, min(args.n, len(corpus)))
    vocab_pool = sorted({w for r in corpus for w in tokenize(r["abstract"]) if len(w) >= 6 and w.isalpha()})

    faithful_scores, faithful_flagged = [], 0
    by_k = {}
    for k in args.k:
        by_k[k] = {"scores": [], "recall_hits": 0, "injected": 0, "weak": 0}
    for r in papers:
        sent = sentences(r["abstract"])
        summary = {"tldr": sent[0], "problem": sent[1], "methods": sent[2], "benchmarks": sent[-1]}
        rep = grounding_report(summary, r["title"], r["abstract"])
        faithful_scores.append(rep["score"])
        faithful_flagged += bool(rep["unsupported"])
        own = set(tokenize(r["title"])) | set(tokenize(r["abstract"]))
        own_stems = {w[:5] for w in own if len(w) >= 5}
        candidates = [w for w in vocab_pool if w not in own and w[:5] not in own_stems]
        for k in args.k:
            fake = rng.sample(candidates, k)
            bad = dict(summary)
            bad["methods"] = summary["methods"] + " using " + " ".join(fake[: (k + 1) // 2])
            bad["benchmarks"] = summary["benchmarks"] + " on " + " ".join(fake[(k + 1) // 2:])
            rep_b = grounding_report(bad, r["title"], r["abstract"])
            flagged = set(rep_b["unsupported"])
            # The report lists at most 10 terms; count injected ones found among all unsupported.
            by_k[k]["recall_hits"] += sum(1 for f in fake if f in flagged)
            by_k[k]["injected"] += k
            by_k[k]["scores"].append(rep_b["score"])
            by_k[k]["weak"] += rep_b["score"] is not None and rep_b["score"] < 0.5

    f = np.asarray([x for x in faithful_scores if x is not None])
    out = {"n_papers": len(papers), "seed": args.seed,
           "faithful": {"mean_score": float(f.mean()), "min_score": float(f.min()),
                        "share_with_any_flag": faithful_flagged / len(papers),
                        "share_weak_below_50pct": float((f < 0.5).mean())},
           "injected": {}}
    lines = [f"# Grounding check on {len(papers)} papers (seed {args.seed})", "",
             f"Faithful summaries (copied from the abstract): mean score {f.mean():.3f}, "
             f"{100 * faithful_flagged / len(papers):.1f}% have any flagged term, "
             f"{100 * (f < 0.5).mean():.1f}% fall under the 50% line.", "",
             "| Injected terms | Recall of injected terms | Mean score | Under 50% line | ROC AUC vs faithful |",
             "|---|---|---|---|---|"]
    for k, d in by_k.items():
        b = np.asarray(d["scores"], dtype=float)
        auc = roc_auc_score([1] * len(f) + [0] * len(b), list(f) + list(b))
        out["injected"][str(k)] = {"recall": d["recall_hits"] / d["injected"], "mean_score": float(b.mean()),
                                   "share_weak_below_50pct": d["weak"] / len(b), "roc_auc": float(auc)}
        lines.append(f"| {k} | {d['recall_hits'] / d['injected']:.3f} | {b.mean():.3f} | "
                     f"{100 * d['weak'] / len(b):.1f}% | {auc:.3f} |")
    if args.db:
        live = live_scores()
        out["stored_llm_summaries"] = live
        lines += ["", f"Stored LLM summaries in the local database (n={live['n']}): mean score "
                  f"{live['mean_score']:.3f}, median {live['median_score']:.3f}, "
                  f"{100 * live['share_weak_below_50pct']:.1f}% under the 50% line, "
                  f"{100 * live['share_with_any_flag']:.1f}% with any flagged term."]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "results.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
