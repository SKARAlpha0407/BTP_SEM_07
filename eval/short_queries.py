"""Short topic queries through the app's own ranking code, for each embedding.

Kavosh is searched with short topics ("graph neural networks"), not titles.
This script builds short queries from the corpus and runs them through the
same ranking steps as /search, once per embedding model:

  1. candidate pool, chosen with --pool:
       bm25  the top POOL papers by BM25 over title + abstract (a stand-in for
             arXiv's keyword search, which cannot be replayed offline);
       full  all corpus papers, so neither BM25 nor the embedding pre-selects
             the candidates (the neutral variant);
  2. dense ranking of the pool by cosine(query, abstract) with the model;
  3. optional hybrid step: backend.app.main._hybrid_reorder (BM25 + RRF);
  4. top 5, scores rescaled by backend.app.main._calibrate_scores;
  5. display order, two variants:
       A  re-sorted by the rescaled dense score (what the app does today)
       B  kept in RRF order.

Two query styles per paper (relevance = the paper the query came from):
  first2  the first two content words of the title
  idf3    the three title words with the highest IDF in the corpus

Metrics on the top 5: hit@1, MRR@5, nDCG@5, recall@5 (own paper in the top
5), and topical precision@5 (share of the top 5 that shares an arXiv
category with the query's paper; base rate printed).

    python -m eval.short_queries --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \\
        intfloat/e5-small-v2 thenlper/gte-small --out eval/results/embedding_study/short_queries
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter

import numpy as np

os.environ.setdefault("GROQ_API_KEY", "offline-eval")  # main.py refuses to import without one

from backend.app.arxiv_client import Paper  # noqa: E402
from backend.app.embedders import get_embedder, tokenize  # noqa: E402
from backend.app.hybrid import BM25  # noqa: E402

from .data import load_corpus  # noqa: E402

POOL = 50
TOP = 5
_STOP = {"with", "from", "that", "this", "using", "towards", "toward", "into", "over", "under",
         "based", "via", "their", "through", "about", "beyond", "when", "what", "does", "your"}


def content_words(title):
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]*", title)
            if len(w) > 3 and w.lower() not in _STOP and w.lower() not in ENGLISH_STOP_WORDS]


def make_queries(corpus):
    df = Counter()
    for r in corpus:
        df.update(set(w.lower() for w in content_words(r["title"])))
    n = len(corpus)
    first2, idf3 = [], []
    for r in corpus:
        words = content_words(r["title"])
        first2.append(" ".join(words[:2]) or r["title"])
        uniq = list(dict.fromkeys(words))
        ranked = sorted(uniq, key=lambda w: -math.log(n / (1 + df[w.lower()])))
        keep = set(ranked[:3])
        idf3.append(" ".join(w for w in uniq if w in keep) or r["title"])
    return {"first2": first2, "idf3": idf3}


def same_topic(corpus):
    cats = [set(r.get("categories") or []) | {r.get("primary_category")} - {None} for r in corpus]
    return cats


def metrics_for(order_ids, target, cats, qcats):
    rank = order_ids.index(target) + 1 if target in order_ids else None
    hit1 = 1.0 if rank == 1 else 0.0
    mrr = 1.0 / rank if rank else 0.0
    ndcg = 1.0 / math.log2(rank + 1) if rank else 0.0
    rec = 1.0 if rank else 0.0
    prec = sum(1 for i in order_ids if cats[i] & qcats) / max(len(order_ids), 1)
    return hit1, mrr, ndcg, rec, prec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="eval/data/corpus.jsonl")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pool", choices=["bm25", "full"], default="bm25")
    args = ap.parse_args()

    from backend.app import main as app  # the app's own ranking helpers

    corpus = load_corpus(args.corpus, args.limit)
    n = len(corpus)
    queries = make_queries(corpus)
    cats = same_topic(corpus)
    base_rate = float(np.mean([[bool(cats[i] & cats[j]) for j in range(n) if j != i] for i in range(n)]))
    papers = [Paper(title=r["title"], authors=[], abstract=r["abstract"], arxiv_id=str(i),
                    arxiv_url="", pdf_url="", published=r.get("published", ""), categories=list(cats[i]))
              for i, r in enumerate(corpus)]
    bm25_all = BM25([f"{r['title']} {r['abstract']}" for r in corpus])

    os.makedirs(args.out, exist_ok=True)
    rows, per_query = [], {}
    for spec in args.models:
        emb = get_embedder(spec)
        doc_vecs = np.vstack([emb.encode_documents([r["abstract"] for r in corpus[i:i + 64]])
                              for i in range(0, n, 64)])
        for style, qs in queries.items():
            q_vecs = np.vstack([emb.encode_queries(qs[i:i + 64]) for i in range(0, n, 64)])
            acc = {k: [] for k in ("dense", "hybrid_A", "hybrid_B")}
            for qi, q in enumerate(qs):
                pool = list(range(n)) if args.pool == "full" else list(np.argsort(-bm25_all.scores(q))[:POOL])
                sims = doc_vecs[pool] @ q_vecs[qi]
                dense_order = [pool[k] for k in np.argsort(-sims, kind="stable")]
                vec_of = {pool[k]: doc_vecs[pool[k]].tolist() for k in range(len(pool))}
                sim_of = {pool[k]: float(sims[k]) for k in range(len(pool))}

                def as_papers(order):
                    out = []
                    for i in order:
                        p = Paper(**{**papers[i].__dict__})
                        p.relevance_score = sim_of[i]
                        out.append(p)
                    return out

                # dense only (HYBRID_RETRIEVAL=0): top 5 by dense, rescaled and sorted
                top = as_papers(dense_order[:TOP])
                app._calibrate_scores(top, q)
                top.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
                acc["dense"].append(metrics_for([int(p.arxiv_id) for p in top], qi, cats, cats[qi]))

                # hybrid: the app's _hybrid_reorder on the dense-ranked pool
                ranked, _ = app._hybrid_reorder(q, as_papers(dense_order), [vec_of[i] for i in dense_order])
                top = ranked[:TOP]
                app._calibrate_scores(top, q)
                acc["hybrid_B"].append(metrics_for([int(p.arxiv_id) for p in top], qi, cats, cats[qi]))
                top_a = sorted(top, key=lambda p: p.relevance_score or 0.0, reverse=True)
                acc["hybrid_A"].append(metrics_for([int(p.arxiv_id) for p in top_a], qi, cats, cats[qi]))

            for variant, vals in acc.items():
                m = np.asarray(vals)
                rows.append({"model": spec, "style": style, "variant": variant,
                             "hit@1": m[:, 0].mean(), "mrr@5": m[:, 1].mean(), "ndcg@5": m[:, 2].mean(),
                             "recall@5": m[:, 3].mean(), "topical_p@5": m[:, 4].mean()})
                per_query[f"{spec.replace('/', '__')}|{style}|{variant}"] = m
            print(f"[{spec}] {style} done", flush=True)

    np.savez_compressed(os.path.join(args.out, "per_query.npz"), **per_query)
    with open(os.path.join(args.out, "results.json"), "w") as fh:
        json.dump({"n_queries": n, "pool": args.pool, "pool_size": POOL if args.pool == "bm25" else n, "top": TOP, "topical_base_rate": base_rate,
                   "examples": {k: v[:5] for k, v in queries.items()}, "rows": rows}, fh, indent=2)
    pool_txt = f"pool {POOL} by BM25" if args.pool == "bm25" else f"pool = all {n} papers"
    lines = [f"# Short topic queries ({n} per style, {pool_txt}, top {TOP})", "",
             f"Topical base rate (random pair shares a category): {base_rate:.3f}", "",
             "| Model | Style | Variant | hit@1 | MRR@5 | nDCG@5 | recall@5 | topical P@5 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['style']} | {r['variant']} | {r['hit@1']:.3f} | {r['mrr@5']:.3f} | "
                     f"{r['ndcg@5']:.3f} | {r['recall@5']:.3f} | {r['topical_p@5']:.3f} |")
    with open(os.path.join(args.out, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
