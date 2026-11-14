"""t-SNE map of paper embeddings, coloured by the arXiv category each paper was fetched for.

The retrieval counterpart of the Sem-6 t-SNE analysis, drawn from real
vectors. A silhouette score (cosine) quantifies how well each embedding model
separates the categories, so the picture comes with a number.

    python -m eval.embedding_map --models all-MiniLM-L6-v2 hash-ngram

Writes eval/results/tsne_<model>.png and eval/results/embedding_map.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re

import numpy as np

from .build_dataset import DEFAULT_CATEGORIES
from .data import load_corpus
from .systems import DenseSystem


def label_for(rec: dict, wanted: list[str]) -> str | None:
    """The category a paper belongs to for the map, or None to drop it.

    Uses the category it was fetched for when the corpus recorded one. Older
    corpora only have arXiv's own categories, whose primary is often a
    cross-listing (astro-ph.IM, cs.AR, ...); taking the first of the paper's
    categories that was queried keeps the map to the requested classes.
    """
    if rec.get("query_category") in wanted:
        return rec["query_category"]
    cats = [rec.get("primary_category")] + list(rec.get("categories") or [])
    return next((c for c in cats if c in wanted), None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--models", nargs="+", default=["all-MiniLM-L6-v2", "hash-ngram"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES,
                    help="classes to colour and score; papers in none of them are dropped")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()

    from sklearn.manifold import TSNE
    from sklearn.metrics import silhouette_score
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    corpus = load_corpus(args.corpus, args.limit)
    tagged = [(r, label_for(r, args.categories)) for r in corpus]
    corpus = [r for r, c in tagged if c is not None]
    labels = [c for _, c in tagged if c is not None]
    cats = sorted(set(labels))
    y = np.array([cats.index(c) for c in labels])
    os.makedirs(args.out, exist_ok=True)
    report = {}

    for spec in args.models:
        system = DenseSystem(spec)
        system.index([r["abstract"] for r in corpus])
        x = system.doc_vecs
        sil = float(silhouette_score(x, y, metric="cosine")) if len(cats) > 1 else float("nan")
        xy = TSNE(n_components=2, metric="cosine", init="random", random_state=args.seed,
                  perplexity=min(30, max(5, len(corpus) // 4))).fit_transform(x)
        report[spec] = {"silhouette_cosine": round(sil, 4), "n": len(corpus), "categories": cats}

        fig, ax = plt.subplots(figsize=(6.5, 5.5))
        cmap = plt.get_cmap("tab10")
        for i, c in enumerate(cats):
            m = y == i
            ax.scatter(xy[m, 0], xy[m, 1], s=12, alpha=0.75, color=cmap(i % 10), label=c)
        ax.set_title(f"t-SNE of abstract embeddings: {spec}\nsilhouette (cosine) = {sil:.3f}")
        ax.set_xticks([]); ax.set_yticks([])
        ax.legend(fontsize=8, markerscale=1.5)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, f"tsne_{re.sub(r'[^A-Za-z0-9]+', '_', spec)}.png"), dpi=160)
        plt.close(fig)
        print(f"{spec}: silhouette={sil:.4f}")

    with open(os.path.join(args.out, "embedding_map.json"), "w") as fh:
        json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main()
