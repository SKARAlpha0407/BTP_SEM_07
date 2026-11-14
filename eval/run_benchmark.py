"""Architecture-controlled retrieval benchmark under query noise.

The Semester-6 experiment, moved from sentiment classification to retrieval:
the corpus, queries, noise and metrics are fixed and ONLY the retrieval system
changes. Noise is applied to the query before each system tokenises it.

    python -m eval.run_benchmark \\
        --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 hash-ngram bm25 \\
                 hybrid:all-MiniLM-L6-v2 \\
        --seeds 42 43 44 45 46

Outputs (in --out, default eval/results/):
    results.csv       one row per (system, noise, intensity, seed)
    summary.json      mean and 95% interval across seeds, plus timings
    summary.md        tables ready to paste into the report
    noise_<kind>.png  nDCG@k versus noise intensity, one line per system
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import defaultdict

import numpy as np

from .data import load_corpus
from .ir_metrics import mean_ci95, ranks_of_targets, summarize
from .noise import INTENSITIES, NOISE_FUNCS, corrupt_queries
from .systems import build_system


def run(corpus, model_specs, noise_kinds, intensities, seeds, k):
    queries = [r["title"] for r in corpus]
    docs = [r["abstract"] for r in corpus]
    targets = list(range(len(corpus)))
    rows, timings = [], {}

    for spec in model_specs:
        system = build_system(spec)
        t0 = time.perf_counter()
        system.index(docs)
        index_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        clean = summarize(ranks_of_targets(system.score(queries), targets), k)
        query_ms = 1000 * (time.perf_counter() - t0) / len(queries)
        timings[system.name] = {
            "family": system.family,
            "index_seconds": round(index_s, 3),
            "ms_per_query": round(query_ms, 3),
        }
        rows.append({"system": system.name, "family": system.family, "noise": "clean",
                     "intensity": 0.0, "seed": seeds[0], **clean})
        print(f"[{system.name}] clean  " + "  ".join(f"{m}={v:.4f}" for m, v in clean.items()))

        for kind in noise_kinds:
            for rho in intensities:
                for seed in seeds:
                    noisy = corrupt_queries(queries, kind, rho, seed)
                    m = summarize(ranks_of_targets(system.score(noisy), targets), k)
                    rows.append({"system": system.name, "family": system.family, "noise": kind,
                                 "intensity": rho, "seed": seed, **m})
            print(f"[{system.name}] {kind} done")
    return rows, timings


def aggregate(rows, metric):
    """{system: {noise: {intensity: (mean, ci)}}} with clean stored at 0.0."""
    bucket = defaultdict(list)
    for r in rows:
        bucket[(r["system"], r["noise"], r["intensity"])].append(r[metric])
    out = defaultdict(lambda: defaultdict(dict))
    for (system, noise, rho), vals in bucket.items():
        out[system][noise][rho] = mean_ci95(vals)
    return out


def write_outputs(rows, timings, out_dir, k, noise_kinds, intensities, meta):
    os.makedirs(out_dir, exist_ok=True)
    fields = list(rows[0].keys())
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    metric = f"ndcg@{k}"
    agg = aggregate(rows, metric)
    systems = list(agg.keys())
    summary = {"meta": meta, "timings": timings, "metric": metric, "systems": {}}
    for s in systems:
        clean = agg[s]["clean"][0.0][0]
        summary["systems"][s] = {"clean": clean, "noise": {}}
        for kind in noise_kinds:
            summary["systems"][s]["noise"][kind] = {
                str(rho): {"mean": agg[s][kind][rho][0], "ci95": agg[s][kind][rho][1]}
                for rho in intensities
            }
    with open(os.path.join(out_dir, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    clean_rows = {r["system"]: r for r in rows if r["noise"] == "clean"}
    lines = [f"# Retrieval benchmark ({meta['n_docs']} papers, {len(meta['seeds'])} noise seeds)", "",
             "## Clean queries", "",
             f"| System | Family | Recall@1 | Recall@{k} | MRR | nDCG@{k} | ms/query |",
             "|---|---|---|---|---|---|---|"]
    for s in systems:
        r = clean_rows[s]
        lines.append(f"| {s} | {r['family']} | {r['recall@1']:.4f} | {r[f'recall@{k}']:.4f} | "
                     f"{r['mrr']:.4f} | {r[metric]:.4f} | {timings[s]['ms_per_query']} |")
    top = max(intensities)
    for kind in noise_kinds:
        shown = [rho for rho in (0.10, 0.30, top) if rho in intensities]
        lines += ["", f"## {metric} under `{kind}` noise", "",
                  "| System | Clean | " + " | ".join(f"@{int(r * 100)}%" for r in shown)
                  + f" | Drop at {int(top * 100)}% |",
                  "|---|---|" + "---|" * (len(shown) + 1)]
        for s in systems:
            clean = agg[s]["clean"][0.0][0]
            cells = [f"{agg[s][kind][rho][0]:.4f} ± {agg[s][kind][rho][1]:.4f}" for rho in shown]
            lines.append(f"| {s} | {clean:.4f} | " + " | ".join(cells)
                         + f" | {agg[s][kind][top][0] - clean:+.4f} |")
    with open(os.path.join(out_dir, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping plots")
        return
    markers = ["o", "s", "^", "D", "v", "P", "X", "*"]
    styles = ["-", "--", "-.", ":"]
    for kind in noise_kinds:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for i, s in enumerate(systems):
            xs = [0.0] + list(intensities)
            ys = [agg[s]["clean"][0.0][0]] + [agg[s][kind][r][0] for r in intensities]
            es = [0.0] + [agg[s][kind][r][1] for r in intensities]
            ax.errorbar([100 * x for x in xs], ys, yerr=es, label=s, capsize=2, linewidth=1.8,
                        marker=markers[i % len(markers)], linestyle=styles[i % len(styles)],
                        markersize=5)
        ax.set_xlabel("Query noise (%)")
        ax.set_ylabel(metric)
        ax.set_title(f"{metric} vs. {kind} noise (mean ± 95% CI over seeds)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"noise_{kind}.png"), dpi=160)
        plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--models", nargs="+",
                    default=["all-MiniLM-L6-v2", "hash-ngram", "bm25", "hybrid:all-MiniLM-L6-v2"])
    ap.add_argument("--noise", nargs="+", default=list(NOISE_FUNCS), choices=list(NOISE_FUNCS))
    ap.add_argument("--intensities", nargs="+", type=float, default=list(INTENSITIES))
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None, help="use only the first N papers")
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()

    corpus = load_corpus(args.corpus, args.limit)
    rows, timings = run(corpus, args.models, args.noise, args.intensities, args.seeds, args.k)
    meta = {"n_docs": len(corpus), "seeds": args.seeds, "k": args.k,
            "corpus": args.corpus, "models": args.models}
    write_outputs(rows, timings, args.out, args.k, args.noise, args.intensities, meta)
    print(f"wrote results to {args.out}/")


if __name__ == "__main__":
    main()
