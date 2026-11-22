"""Report figures from the result files in eval/results/embedding_study/.

Every number drawn here is read from a results file written by the
corresponding eval script; nothing is typed in by hand.

    python -m eval.report_figures [--benchmark]
"""
from __future__ import annotations

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

R = "eval/results/embedding_study"
OUT = "report/Figures/Ch04"
MODELS = ["all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2", "thenlper/gte-small"]
SHORT = {"all-MiniLM-L6-v2": "MiniLM", "BAAI/bge-small-en-v1.5": "bge-small", "intfloat/e5-small-v2": "e5-small",
         "thenlper/gte-small": "gte-small", "bm25": "BM25", "char-tfidf": "char TF-IDF"}
# Validated categorical palette (dataviz reference, light mode), fixed order.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, MUTED, GRID = "#1f2328", "#5f6670", "#e6e8eb"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.bbox": "tight", "savefig.dpi": 200,
})


def load(path):
    with open(os.path.join(R, path)) as fh:
        return json.load(fh)


def bar_labels(ax, bars, fmt="{:.2f}"):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 2), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7, color=INK)


def grouped(ax, groups, series, values, colors, ylim=None, fmt="{:.2f}"):
    n = len(series)
    w = 0.8 / n
    x = np.arange(len(groups))
    for i, (s, col) in enumerate(zip(series, colors)):
        bars = ax.bar(x + (i - (n - 1) / 2) * w, values[i], w * 0.92, label=s, color=col)
        bar_labels(ax, bars, fmt)
    ax.set_xticks(x, groups)
    ax.grid(axis="x", visible=False)
    if ylim:
        ax.set_ylim(*ylim)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"))
    plt.close(fig)
    print("wrote", name)


def short_queries():
    d = load("short_queries/results.json")
    rows = {(r["model"], r["style"], r["variant"]): r for r in d["rows"]}
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True)
    for ax, style, title in zip(axes, ("first2", "idf3"), ("Two-word topics (first two content words)",
                                                            "Three distinctive title words")):
        vals = [[rows[(m, style, v)]["mrr@5"] for m in MODELS] for v in ("dense", "hybrid_B", "hybrid_A")]
        grouped(ax, [SHORT[m] for m in MODELS], ["Dense only", "Hybrid, fused order", "Hybrid, re-sorted by dense score"],
                vals, [C[0], C[2], C[1]], ylim=(0, 1.05))
        ax.set_title(title, fontsize=9, color=INK)
        ax.set_ylabel("MRR@5")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=8)
    save(fig, "short_queries_mrr")


def app_effect():
    d = load("app_effect/results.json")["summary"]
    others = MODELS[1:]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    ax = axes[0]
    bars = ax.bar([SHORT[m] for m in others], [d[m]["top5_jaccard_vs_default"] for m in others], 0.55, color=C[0])
    bar_labels(ax, bars)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Top-5 overlap with MiniLM (Jaccard)")
    ax.set_title("Same 20 topics, same candidates", fontsize=9, color=INK)
    ax.grid(axis="x", visible=False)
    ax = axes[1]
    bars = ax.bar([SHORT[m] for m in MODELS], [d[m]["top1_cos"] for m in MODELS], 0.55, color=C[1])
    bar_labels(ax, bars)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean top-1 cosine")
    ax.set_title("Score scale differs by model", fontsize=9, color=INK)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    save(fig, "app_effect")


def clustering():
    d = load("clustering/results.json")["results"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    grouped(axes[0], [SHORT[m] for m in MODELS], ["Connected components", "Modularity"],
            [[d[m]["components"]["nmi"] for m in MODELS], [d[m]["modularity"]["nmi"] for m in MODELS]],
            [C[1], C[0]], ylim=(0, 1))
    axes[0].set_ylabel("NMI with arXiv category")
    grouped(axes[1], [SHORT[m] for m in MODELS], ["Connected components", "Modularity"],
            [[d[m]["components"]["largest"] for m in MODELS], [d[m]["modularity"]["largest"] for m in MODELS]],
            [C[1], C[0]], ylim=(0, 1.05))
    axes[1].set_ylabel("Share of papers in largest cluster")
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.1, -0.12), ncol=2, fontsize=8)
    save(fig, "clustering")


def cache():
    rows = []
    for m in MODELS:
        d = load(f"thresholds/{m.replace('/', '_')}.json")["short_query"]["cache_replay"]
        rows.append((d["served_fraction"], d["served_hits_on_topic"],
                     d["shipped_defaults"]["served_fraction"], d["shipped_defaults"]["served_hits_on_topic"]))
    rows = np.asarray(rows)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    grouped(axes[0], [SHORT[m] for m in MODELS], ["Thresholds measured for the model", "Shipped defaults (0.40 / 0.35)"],
            [rows[:, 0], rows[:, 2]], [C[0], C[1]], ylim=(0, 1.1))
    axes[0].set_ylabel("Short queries served from cache")
    grouped(axes[1], [SHORT[m] for m in MODELS], ["Measured", "Shipped"],
            [rows[:, 1], rows[:, 3]], [C[0], C[1]], ylim=(0, 1))
    axes[1].axhline(0.349, color=MUTED, linewidth=1, linestyle="--")
    axes[1].text(1.01, 0.349, "base rate\n0.35", transform=axes[1].get_yaxis_transform(), fontsize=7,
                 color=MUTED, va="center", ha="left", clip_on=False)
    axes[1].set_ylabel("Served hits on-topic")
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.1, -0.12), ncol=2, fontsize=8)
    save(fig, "cache_thresholds")


def grounding():
    d = load("grounding/results.json")
    ks = sorted(int(k) for k in d["injected"])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    ax = axes[0]
    ax.plot([0] + ks, [d["faithful"]["mean_score"]] + [d["injected"][str(k)]["mean_score"] for k in ks],
            color=C[0], marker="o", markersize=5, linewidth=2, label="Mean grounding score")
    ax.plot(ks, [d["injected"][str(k)]["recall"] for k in ks], color=C[1], marker="s",
            markersize=5, linewidth=2, label="Injected terms flagged")
    ax.axhline(0.5, color=MUTED, linewidth=1, linestyle="--")
    ax.annotate("app's 'weak' line", (5, 0.52), fontsize=7, color=MUTED, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Foreign terms injected into a faithful summary")
    ax.legend(fontsize=7.5, loc="lower left")
    ax = axes[1]
    s = d.get("stored_llm_summaries")
    if s:
        names = ["mean", "median", "10th pct."]
        bars = ax.bar(names, [s["mean_score"], s["median_score"], s["p10_score"]], 0.5, color=C[2])
        bar_labels(ax, bars)
        ax.set_ylim(0, 1)
        ax.set_title(f"Real LLM summaries (n={s['n']})", fontsize=9, color=INK)
        ax.set_ylabel("Grounding score")
        ax.grid(axis="x", visible=False)
    fig.tight_layout()
    save(fig, "grounding")


def benchmark():
    s = json.load(open(os.path.join(R, "benchmark/summary.json")))
    systems = s["systems"]
    kinds = ("char", "dropout", "oov")
    titles = {"char": "Character noise", "dropout": "Word dropout", "oov": "Out-of-vocabulary injection"}
    groups = [("dense", ["all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2", "thenlper/gte-small",
                         "bm25", "char-tfidf"]),
              ("hybrid", ["hybrid:all-MiniLM-L6-v2", "hybrid:BAAI/bge-small-en-v1.5", "hybrid:intfloat/e5-small-v2",
                          "hybrid:thenlper/gte-small", "bm25"])]
    for tag, names in groups:
        names = [n for n in names if n in systems]
        fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.7), sharey=True)
        for ax, kind in zip(axes, kinds):
            for i, n in enumerate(names):
                rhos = sorted(float(r) for r in systems[n]["noise"][kind])
                ys = [systems[n]["clean"]] + [systems[n]["noise"][kind][str(r)]["mean"] for r in rhos]
                es = [0] + [systems[n]["noise"][kind][str(r)]["ci95"] for r in rhos]
                base = n.split(":", 1)[-1]
                col = C[MODELS.index(base)] if base in MODELS else (C[4] if n == "bm25" else C[5])
                ls = "--" if n in ("bm25", "char-tfidf") else "-"
                ax.errorbar([0] + [100 * r for r in rhos], ys, yerr=es, color=col, linestyle=ls, linewidth=1.8,
                            marker="o", markersize=3.5, capsize=2, label=SHORT.get(base, base) + (" (hybrid)" if n.startswith("hybrid:") else ""))
            ax.set_title(titles[kind], fontsize=9, color=INK)
            ax.set_xlabel("Words corrupted (%)")
        axes[0].set_ylabel("nDCG@10")
        axes[0].legend(loc="upper center", bbox_to_anchor=(1.6, -0.2), ncol=3, fontsize=7.5)
        save(fig, f"noise_curves_{tag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", action="store_true")
    a = ap.parse_args()
    short_queries()
    app_effect()
    clustering()
    cache()
    grounding()
    if a.benchmark:
        benchmark()


if __name__ == "__main__":
    main()
