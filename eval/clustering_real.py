"""Map clustering on the 20 frozen real topics (eval/app_effect.py candidates).

For each embedding model and topic, the application's ranking is run on the
frozen candidates and the top 30 papers are mapped with backend/app/graph.py
(real author lists, so all three link terms are active). The map is clustered
by connected components and by greedy modularity at resolutions 0.5, 1.0 (the
app's setting) and 1.5.

Agreement is measured against each paper's primary arXiv category. This label
is coarse: one topic's 30 papers often share one or two categories, and a
category says nothing about sub-topics, so NMI here rewards splitting along
category lines only. Reported per model: mean over topics of clusters,
multi-paper clusters, largest-cluster share, NMI, and a Wilcoxon test of
modularity (1.0) against components over the 20 topics.

    python -m eval.clustering_real --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \\
        intfloat/e5-small-v2 thenlper/gte-small
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

os.environ.setdefault("GROQ_API_KEY", "offline-eval")

OUT = "eval/results/embedding_study/clustering_real"
CANDS = "eval/results/embedding_study/app_effect/candidates.jsonl"
METHODS = [("components", 1.0), ("modularity", 0.5), ("modularity", 1.0), ("modularity", 1.5)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True)
    args = ap.parse_args()
    from scipy.stats import wilcoxon
    from sklearn.metrics import normalized_mutual_info_score

    from backend.app import graph
    from backend.app import main as app
    from backend.app.arxiv_client import Paper
    from backend.app.embedders import get_embedder

    topics = [json.loads(l) for l in open(CANDS)]
    results = {}
    for spec in args.models:
        emb = get_embedder(spec)
        acc = {f"{m}@{r}": {k: [] for k in ("clusters", "multi", "largest", "nmi")} for m, r in METHODS}
        label_counts = []
        for t in topics:
            papers = [Paper(**{k: v for k, v in p.items() if k in Paper.__dataclass_fields__}) for p in t["papers"]]
            docs = emb.encode_documents([p.abstract for p in papers])
            q = emb.encode_queries([t["topic"]])[0]
            sims = docs @ q
            order = list(np.argsort(-sims, kind="stable"))
            ranked = []
            for i in order:
                p = Paper(**{**papers[i].__dict__})
                p.relevance_score = float(sims[i])
                ranked.append(p)
            ranked, _ = app._hybrid_reorder(t["topic"], ranked, [docs[i].tolist() for i in order])
            gp = ranked[:30]
            v = emb.encode_documents([p.abstract for p in gp])
            nodes = graph.build_nodes(gp)
            links = graph.build_links(gp, nodes, v @ v.T)
            labels = [p.categories[0] if p.categories else "none" for p in gp]
            label_counts.append(len(set(labels)))
            for m, r in METHODS:
                g = graph.cluster(len(gp), links, m, r)
                assign = [0] * len(gp)
                for cid, members in g.items():
                    for x in members:
                        assign[x] = cid
                sizes = sorted((len(c) for c in g.values()), reverse=True)
                a = acc[f"{m}@{r}"]
                a["clusters"].append(len(g)); a["multi"].append(sum(1 for s in sizes if s > 1))
                a["largest"].append(sizes[0] / len(gp)); a["nmi"].append(normalized_mutual_info_score(labels, assign))
        comp, mod = np.asarray(acc["components@1.0"]["nmi"]), np.asarray(acc["modularity@1.0"]["nmi"])
        d = mod - comp
        results[spec] = {"distinct_primary_categories_per_topic": float(np.mean(label_counts)),
                         **{k: {kk: float(np.mean(vv)) for kk, vv in a.items()} for k, a in acc.items()},
                         "nmi_gain_mod1_vs_components": float(d.mean()),
                         "topics_better_worse_tied": [int((d > 0).sum()), int((d < 0).sum()), int((d == 0).sum())],
                         "wilcoxon_p": float(wilcoxon(d).pvalue) if np.any(d) else 1.0}
        print(f"[{spec}] done", flush=True)
    lines = [f"# Map clustering on {len(topics)} real topics (top 30 papers each)", "",
             "Labels: primary arXiv category (coarse). Modularity: greedy (Clauset-Newman-Moore), networkx.", "",
             "| Model | Method | Clusters | Multi-paper | Largest share | NMI |", "|---|---|---|---|---|---|"]
    for spec, r in results.items():
        for m, res in METHODS:
            x = r[f"{m}@{res}"]
            name = "components" if m == "components" else f"modularity, resolution {res}"
            lines.append(f"| {spec} | {name} | {x['clusters']:.1f} | {x['multi']:.1f} | {x['largest']:.2f} | {x['nmi']:.3f} |")
        b, w, t_ = r["topics_better_worse_tied"]
        lines.append(f"| {spec} | modularity 1.0 − components | | | | {r['nmi_gain_mod1_vs_components']:+.3f} "
                     f"(better on {b}, worse on {w}, tied {t_}; Wilcoxon p={r['wilcoxon_p']:.2g}) |")
        lines.append(f"| {spec} | distinct primary categories per topic | | | | {r['distinct_primary_categories_per_topic']:.1f} |")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"topics": len(topics), "results": results}, open(os.path.join(OUT, "results.json"), "w"), indent=2)
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
