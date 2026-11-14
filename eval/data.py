"""Corpus loading for the evaluation scripts (JSON Lines)."""
from __future__ import annotations

import json
from typing import Dict, List


def load_corpus(path: str, limit: int | None = None) -> List[Dict]:
    rows, seen = [], set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("title") and row.get("abstract") and row["arxiv_id"] not in seen:
                seen.add(row["arxiv_id"])
                rows.append(row)
            if limit and len(rows) >= limit:
                break
    if not rows:
        raise SystemExit(f"{path} has no usable rows; run `python -m eval.build_dataset` first")
    return rows
