"""How the choice of embedding changes what Kavosh shows, on real topics.

Step 1 (network, once): fetch arXiv candidates for a fixed list of topics with
the app's own client and freeze them in candidates.jsonl, so every model sees
exactly the same papers.

Step 2 (offline): for each embedding model and topic, run the app's ranking
(dense cosine, then main._hybrid_reorder with BM25 + RRF), take the top 5 and
the top 30 for the reading map, and build the map with backend/app/graph.py.

Reported per model (averaged over topics):
  - agreement with the default model (all-MiniLM-L6-v2): Jaccard overlap of
    the top-5 sets, Kendall tau of the full candidate ranking, Jaccard of the
    map's link sets;
  - the raw cosine scale: top-1 and top-5 mean cosine (scores feed the fixed
    display rescaling and cache thresholds, which were tuned for MiniLM);
  - the map: links, isolated papers, clusters and largest-cluster share for
    connected components and for greedy modularity, and the agreement (NMI)
    of each clustering with the papers' primary arXiv category.

There is no relevance judgement here: this measures how much the app changes,
not which model is right (see eval/short_queries.py and eval/run_benchmark.py
for quality).

    python -m eval.app_effect fetch
    python -m eval.app_effect run --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \\
        intfloat/e5-small-v2 thenlper/gte-small
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations

import numpy as np

os.environ.setdefault("GROQ_API_KEY", "offline-eval")

OUT = "eval/results/embedding_study/app_effect"
TOPICS = [
    "retrieval augmented generation", "diffusion models for video", "graph neural networks",
    "LLM evaluation", "vision transformers", "federated learning privacy",
    "reinforcement learning from human feedback", "speech recognition",
    "protein structure prediction", "neural radiance fields",
    "spiking neural networks for event cameras", "knowledge distillation",
    "contrastive learning", "time series forecasting", "autonomous driving perception",
    "code generation with large language models", "medical image segmentation",
    "recommender systems", "quantum machine learning", "explainable AI",
]
DEFAULT = "all-MiniLM-L6-v2"


def fetch(path):
    from backend.app.arxiv_client import search_papers

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for t in TOPICS:
            papers = search_papers(t)
            fh.write(json.dumps({"topic": t, "papers": [p.__dict__ for p in papers]}) + "\n")
            print(f"{t}: {len(papers)} candidates", flush=True)


def kendall(a, b):
    from scipy.stats import kendalltau

    pos = {x: i for i, x in enumerate(b)}
    return kendalltau(range(len(a)), [pos[x] for x in a]).statistic


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def nmi(groups, labels):
    from sklearn.metrics import normalized_mutual_info_score

    assign = {}
    for cid, members in groups.items():
        for m in members:
            assign[m] = cid
    return normalized_mutual_info_score([labels[i] for i in range(len(labels))], [assign[i] for i in range(len(labels))])


def run(path, models):
    from backend.app import graph
    from backend.app import main as app
    from backend.app.arxiv_client import Paper
    from backend.app.embedders import get_embedder

    topics = [json.loads(l) for l in open(path)]
    per = {m: [] for m in models}
    orders = {}
    for spec in models:
        emb = get_embedder(spec)
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
            ids = [p.arxiv_id for p in ranked]
            top5 = ids[:5]
            gp = ranked[:30]
            gvec = emb.encode_documents([p.abstract for p in gp])
            nodes = graph.build_nodes(gp)
            links = graph.build_links(gp, nodes, gvec @ gvec.T)
            edges = {tuple(sorted((gp[l["source"]].arxiv_id, gp[l["target"]].arxiv_id))) for l in links}
            labels = [(p.categories[0] if p.categories else "") for p in gp]
            rec = {"topic": t["topic"], "n_candidates": len(papers), "top5": top5, "order": ids,
                   "edges": edges, "top1_cos": float(sims.max()), "top5_cos": float(np.sort(sims)[-5:].mean()),
                   "links": len(links), "isolated": sum(1 for n in nodes if n["degree"] == 0)}
            for method in ("components", "modularity"):
                g = graph.cluster(len(gp), links, method)
                sizes = sorted((len(v) for v in g.values()), reverse=True)
                rec[f"{method}_clusters"] = len(g)
                rec[f"{method}_multi"] = sum(1 for s in sizes if s > 1)
                rec[f"{method}_largest"] = sizes[0] / len(gp)
                rec[f"{method}_nmi"] = nmi(g, labels)
            per[spec].append(rec)
            orders[(spec, t["topic"])] = rec
        print(f"[{spec}] done", flush=True)

    summary = {}
    for spec in models:
        recs = per[spec]
        s = {k: float(np.mean([r[k] for r in recs])) for k in
             ("n_candidates", "top1_cos", "top5_cos", "links", "isolated",
              "components_clusters", "components_multi", "components_largest", "components_nmi",
              "modularity_clusters", "modularity_multi", "modularity_largest", "modularity_nmi")}
        if spec != DEFAULT and DEFAULT in models:
            base = {r["topic"]: r for r in per[DEFAULT]}
            s["top5_jaccard_vs_default"] = float(np.mean([jaccard(r["top5"], base[r["topic"]]["top5"]) for r in recs]))
            s["kendall_vs_default"] = float(np.mean([kendall(r["order"], base[r["topic"]]["order"]) for r in recs]))
            s["edge_jaccard_vs_default"] = float(np.mean([jaccard(r["edges"], base[r["topic"]]["edges"]) for r in recs]))
        summary[spec] = s
    pair = {}
    for a, b in combinations(models, 2):
        pair[f"{a} vs {b}"] = float(np.mean([jaccard(orders[(a, t['topic'])]["top5"], orders[(b, t['topic'])]["top5"]) for t in topics]))
    stable5 = float(np.mean([len(set.intersection(*(set(orders[(m, t['topic'])]["top5"]) for m in models))) for t in topics]))

    os.makedirs(OUT, exist_ok=True)
    out = {"topics": [t["topic"] for t in topics], "summary": summary, "top5_jaccard_pairs": pair,
           "papers_in_every_models_top5": stable5,
           "per_topic": {m: [{k: v for k, v in r.items() if k not in ("order", "edges")} for r in per[m]] for m in models}}
    with open(os.path.join(OUT, "results.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps({"summary": summary, "pairs": pair, "in_every_top5": stable5}, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "run"])
    ap.add_argument("--candidates", default=os.path.join(OUT, "candidates.jsonl"))
    ap.add_argument("--models", nargs="+", default=[DEFAULT])
    args = ap.parse_args()
    if args.step == "fetch":
        fetch(args.candidates)
    else:
        run(args.candidates, args.models)


if __name__ == "__main__":
    sys.exit(main())
