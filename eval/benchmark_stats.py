"""Paired significance tests on the benchmark's per-query ranks.

For each comparison and condition, the per-query reciprocal rank (averaged over
the noise seeds) of system A is compared with system B by a two-sided Wilcoxon
signed-rank test. Also reports relative nDCG@10 loss at 50% noise per system.

    python -m eval.benchmark_stats
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy.stats import wilcoxon

R = "eval/results/embedding_study/benchmark"
MODELS = ["all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2", "thenlper/gte-small"]


def key(s):
    return s.replace("/", "__")


def rr(ranks, system, noise, rho):
    if noise == "clean":
        return 1.0 / ranks[f"{key(system)}|clean|0.0|42"]
    arrs = [1.0 / ranks[k] for k in ranks.files if k.startswith(f"{key(system)}|{noise}|{rho}|")]
    return np.mean(arrs, axis=0)


def main():
    ranks = np.load(os.path.join(R, "ranks.npz"))
    summary = json.load(open(os.path.join(R, "summary.json")))["systems"]
    conds = [("clean", 0.0)] + [(n, 0.5) for n in ("char", "dropout", "oov")]
    comps = []
    for m in MODELS:
        comps.append((m, "all-MiniLM-L6-v2") if m != "all-MiniLM-L6-v2" else None)
        comps.append((m, "bm25"))
        comps.append((f"hybrid:{m}", m))
        comps.append((f"hybrid:{m}", "bm25"))
    comps.append(("char-tfidf", "bm25"))
    comps = [c for c in comps if c]
    out = []
    for a, b in comps:
        for noise, rho in conds:
            x, y = rr(ranks, a, noise, rho), rr(ranks, b, noise, rho)
            d = x - y
            p = float(wilcoxon(d).pvalue) if np.any(d) else 1.0
            out.append({"a": a, "b": b, "noise": noise, "rho": rho, "mrr_a": float(x.mean()), "mrr_b": float(y.mean()),
                        "diff": float(d.mean()), "a_better": int((d > 0).sum()), "b_better": int((d < 0).sum()), "p": p})
    rel = {}
    for s, v in summary.items():
        rel[s] = {n: (v["clean"] - v["noise"][n]["0.5"]["mean"]) / v["clean"] for n in ("char", "dropout", "oov")}
    with open(os.path.join(R, "stats.json"), "w") as fh:
        json.dump({"tests": out, "relative_loss_at_50pct": rel}, fh, indent=2)
    lines = ["# Paired Wilcoxon tests on per-query reciprocal rank (mean over seeds)", "",
             "| A | B | Condition | MRR A | MRR B | A − B | A better / B better (queries) | p |", "|---|---|---|---|---|---|---|---|"]
    for r in out:
        cond = "clean" if r["noise"] == "clean" else f"{r['noise']} 50%"
        lines.append(f"| {r['a']} | {r['b']} | {cond} | {r['mrr_a']:.3f} | {r['mrr_b']:.3f} | {r['diff']:+.3f} | "
                     f"{r['a_better']} / {r['b_better']} | {r['p']:.1e} |")
    lines += ["", "# Relative nDCG@10 loss at 50% noise", "", "| System | char | dropout | oov |", "|---|---|---|---|"]
    for s, v in rel.items():
        lines.append(f"| {s} | {100 * v['char']:.1f}% | {100 * v['dropout']:.1f}% | {100 * v['oov']:.1f}% |")
    with open(os.path.join(R, "stats.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
