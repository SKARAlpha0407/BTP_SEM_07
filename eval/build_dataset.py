"""Build the evaluation corpus from arXiv.

Known-item retrieval: each paper's TITLE is the query and its ABSTRACT is the
only relevant document, so relevance labels come for free and need no manual
annotation. Titles never appear in the indexed text.

    python -m eval.build_dataset --per-category 150

Writes eval/data/corpus.jsonl (one paper per line). Respects arXiv's rate
limit (one request every 3 seconds), so 6 categories take about a minute.
"""
from __future__ import annotations

import argparse
import json
import os

DEFAULT_CATEGORIES = ["cs.CL", "cs.LG", "cs.CV", "cs.IR", "cs.RO", "stat.ML"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES)
    ap.add_argument("--per-category", type=int, default=150)
    ap.add_argument("--out", default="eval/data/corpus.jsonl")
    args = ap.parse_args()

    import arxiv

    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=5)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    seen, n = set(), 0
    with open(args.out, "w", encoding="utf-8") as fh:
        for cat in args.categories:
            search = arxiv.Search(
                query=f"cat:{cat}",
                max_results=args.per_category,
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )
            got = 0
            for r in client.results(search):
                arxiv_id = r.entry_id.split("/")[-1]
                if arxiv_id in seen:
                    continue
                seen.add(arxiv_id)
                fh.write(json.dumps({
                    "arxiv_id": arxiv_id,
                    "title": " ".join(r.title.split()),
                    "abstract": " ".join(r.summary.split()),
                    "categories": list(r.categories),
                    "primary_category": r.primary_category,
                    "published": r.published.strftime("%Y-%m-%d"),
                }) + "\n")
                got += 1
                n += 1
            print(f"{cat}: {got} papers")
    print(f"wrote {n} papers to {args.out}")


if __name__ == "__main__":
    main()
