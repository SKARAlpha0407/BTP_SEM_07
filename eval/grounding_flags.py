"""Hand-labelling sheet for the term-overlap check's flags, and its precision.

  python -m eval.grounding_flags sheet   # write a CSV of 100 sampled flags
  python -m eval.grounding_flags score   # precision from the filled-in CSV

Each row is one flagged term from a real LLM summary stored by the app, with
the summary field it came from and the paper's abstract. A person fills the
`label` column with one of:

  invented     not supported by the abstract (a real error the flag should catch)
  paraphrase   the abstract says the same thing in other words
  inferable    a reasonable generalisation or common term (e.g. "model")
  present      the idea or word is in the abstract (missed by tokenisation)

Precision = invented / labelled rows.
"""
from __future__ import annotations

import csv
import os
import random
import sys
from collections import Counter

OUT = "eval/results/embedding_study/grounding/flag_labelling_sheet.csv"
LABELS = ("invented", "paraphrase", "inferable", "present")


def sheet(n=100, seed=11):
    from sqlalchemy import text

    from backend.app.db.connection import SessionLocal
    from backend.app.grounding import grounding_report

    with SessionLocal() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        rows = s.execute(text(
            "SELECT p.arxiv_id, p.title, p.abstract, i.tldr, i.problem, i.methods, i.benchmarks "
            "FROM paper_insights i JOIN papers p USING (arxiv_id) ORDER BY p.arxiv_id")).fetchall()
        s.rollback()
    flags = []
    for aid, title, abstract, *fields in rows:
        summary = dict(zip(("tldr", "problem", "methods", "benchmarks"), fields))
        for term in grounding_report(summary, title, abstract)["unsupported"]:
            field = next((f for f, v in summary.items() if v and term in v.lower()), "")
            flags.append({"arxiv_id": aid, "title": title, "term": term, "field": field,
                          "field_text": summary.get(field, ""), "abstract": abstract, "label": "", "note": ""})
    random.Random(seed).shuffle(flags)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()))
        w.writeheader()
        w.writerows(flags[:n])
    print(f"{len(flags)} flags in {len(rows)} summaries; wrote {min(n, len(flags))} to {OUT}")


def score():
    with open(OUT) as fh:
        rows = [r for r in csv.DictReader(fh) if r["label"].strip()]
    bad = [r["label"] for r in rows if r["label"].strip() not in LABELS]
    if bad:
        raise SystemExit(f"unknown labels: {set(bad)}; use one of {LABELS}")
    c = Counter(r["label"].strip() for r in rows)
    n = len(rows)
    print(f"labelled {n}: " + ", ".join(f"{k} {c[k]}" for k in LABELS))
    if n:
        print(f"precision (invented / labelled) = {c['invented'] / n:.3f}")


if __name__ == "__main__":
    {"sheet": sheet, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "sheet"]()
