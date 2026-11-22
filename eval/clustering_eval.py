"""Which clustering should the reading map use? Tested on corpus subsets.

The corpus was fetched from six arXiv categories (cs.CL, cs.LG, cs.CV, cs.IR,
cs.RO, stat.ML). The label of a paper is its primary arXiv category when that
is one of the six, otherwise "other" (the corpus file does not record which
category query returned each paper).
For each embedding model, SUBSETS random 30-paper maps are built with the app's
own code (backend/app/graph.py: same link weights and threshold) and clustered
two ways:

  components  connected components of the link graph (the current app)
  modularity  greedy modularity communities on the weighted links

Reported (mean over subsets): number of clusters, clusters with more than one
paper, share of papers in the largest cluster, isolated papers, and agreement
with the known categories (NMI and adjusted Rand index). The corpus has no
author lists, so the shared-author term of the link weight is always 0 here.

    python -m eval.clustering_eval --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \\
        intfloat/e5-small-v2 thenlper/gte-small
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

import numpy as np

from backend.app import graph
from backend.app.arxiv_client import Paper
from backend.app.embedders import get_embedder

from .data import load_corpus

OUT = "eval/results/embedding_study/clustering"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--subsets", type=int, default=100)
    ap.add_argument("--size", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    corpus = load_corpus(args.corpus)
    papers = [Paper(title=r["title"], authors=[], abstract=r["abstract"], arxiv_id=r["arxiv_id"], arxiv_url="",
                    pdf_url="", published=r.get("published", ""), categories=list(r.get("categories") or []))
              for r in corpus]
    six = {"cs.CL", "cs.LG", "cs.CV", "cs.IR", "cs.RO", "stat.ML"}
    labels = [r.get("primary_category") if r.get("primary_category") in six else "other" for r in corpus]
    rng = random.Random(args.seed)
    subsets = [rng.sample(range(len(corpus)), args.size) for _ in range(args.subsets)]

    results = {}
    for spec in args.models:
        emb = get_embedder(spec)
        vecs = np.vstack([emb.encode_documents([r["abstract"] for r in corpus[i:i + 64]])
                          for i in range(0, len(corpus), 64)])
        acc = {m: {k: [] for k in ("clusters", "multi", "largest", "isolated", "nmi", "ari")}
               for m in ("components", "modularity")}
        links_n = []
        for idx in subsets:
            sub = [papers[i] for i in idx]
            nodes = graph.build_nodes(sub)
            v = vecs[idx]
            links = graph.build_links(sub, nodes, v @ v.T)
            links_n.append(len(links))
            truth = [labels[i] for i in idx]
            for m in acc:
                g = graph.cluster(len(sub), links, m)
                assign = [0] * len(sub)
                for cid, members in g.items():
                    for x in members:
                        assign[x] = cid
                sizes = sorted((len(c) for c in g.values()), reverse=True)
                acc[m]["clusters"].append(len(g))
                acc[m]["multi"].append(sum(1 for s in sizes if s > 1))
                acc[m]["largest"].append(sizes[0] / len(sub))
                acc[m]["isolated"].append(sum(1 for n in nodes if n["degree"] == 0))
                acc[m]["nmi"].append(normalized_mutual_info_score(truth, assign))
                acc[m]["ari"].append(adjusted_rand_score(truth, assign))
        results[spec] = {"links": float(np.mean(links_n)),
                         **{m: {k: float(np.mean(v)) for k, v in d.items()} for m, d in acc.items()},
                         "nmi_diff_per_subset": [b - a for a, b in zip(acc["components"]["nmi"], acc["modularity"]["nmi"])]}
        print(f"[{spec}] done", flush=True)

    from scipy.stats import wilcoxon

    lines = [f"# Reading-map clustering on {args.subsets} random {args.size}-paper subsets (seed {args.seed})", "",
             "| Model | Method | Links | Clusters | Multi-paper clusters | Largest cluster share | Isolated | NMI | ARI |",
             "|---|---|---|---|---|---|---|---|---|"]
    for spec, r in results.items():
        for m in ("components", "modularity"):
            x = r[m]
            lines.append(f"| {spec} | {m} | {r['links']:.1f} | {x['clusters']:.1f} | {x['multi']:.1f} | "
                         f"{x['largest']:.2f} | {x['isolated']:.1f} | {x['nmi']:.3f} | {x['ari']:.3f} |")
        d = r.pop("nmi_diff_per_subset")
        r["nmi_gain_mean"] = float(np.mean(d))
        r["nmi_gain_wilcoxon_p"] = float(wilcoxon(d).pvalue) if any(d) else 1.0
        lines.append(f"| {spec} | modularity − components NMI | | | | | | {r['nmi_gain_mean']:+.3f} (Wilcoxon p={r['nmi_gain_wilcoxon_p']:.2g}) | |")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "results.json"), "w") as fh:
        json.dump({"subsets": args.subsets, "size": args.size, "seed": args.seed, "results": results}, fh, indent=2)
    with open(os.path.join(OUT, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
