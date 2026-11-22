"""Print what each noise type does to one real title (for the report).

    python -m eval.noise_examples
"""
from __future__ import annotations

import json
import os
import sys

from .data import load_corpus
from .noise import corrupt_queries

OUT = "eval/results/embedding_study/noise_examples.json"


def main():
    corpus = load_corpus("eval/data/corpus.jsonl")
    title = corpus[0]["title"]
    rows = [{"noise": "clean", "rho": 0.0, "query": title}]
    for kind in ("char", "dropout", "oov"):
        for rho in (0.1, 0.3, 0.5):
            rows.append({"noise": kind, "rho": rho, "query": corrupt_queries([title], kind, rho, seed=42)[0]})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(rows, fh, indent=2)
    for r in rows:
        print(f"{r['noise']:8s} {r['rho']:.1f}  {r['query']}")


if __name__ == "__main__":
    sys.exit(main())
