"""Grounding check for LLM-extracted insights.

Flags content words and numbers in an insight that do not appear in the
paper's title or abstract. A low score means the LLM probably invented a
benchmark or method name. It is a lexical heuristic, not a fact-checker.
"""
from __future__ import annotations

from typing import Any, Dict

from .embedders import tokenize

_STOP = {
    "this", "that", "with", "from", "which", "their", "these", "those", "using", "used",
    "paper", "proposes", "propose", "proposed", "presents", "present", "method", "methods",
    "approach", "results", "result", "show", "shows", "shown", "model", "models", "based",
    "study", "work", "authors", "novel", "problem", "task", "tasks", "data", "into", "over",
    "than", "such", "also", "been", "have", "they", "more", "most", "across", "between",
    "evaluated", "evaluate", "evaluation", "benchmark", "benchmarks", "dataset", "datasets",
    "performance", "improve", "improves", "improved", "introduces", "introduce", "address",
    "addresses", "achieves", "achieve", "none", "mentioned", "specified", "reported",
}
_FIELDS = ("tldr", "problem", "methods", "benchmarks")


def _content_terms(text: str) -> set:
    return {
        t for t in tokenize(text)
        if (len(t) >= 4 or t.isdigit()) and t not in _STOP
    }


def grounding_report(insight: Dict[str, Any], title: str, abstract: str) -> Dict[str, Any]:
    """Return {"score": 0..1, "unsupported": [terms]} for one insight dict."""
    source = set(tokenize(title)) | set(tokenize(abstract))
    terms: set = set()
    for f in _FIELDS:
        v = insight.get(f) if isinstance(insight, dict) else None
        if isinstance(v, str) and v.strip() and v.strip().upper() not in {"N/A", "ERROR"}:
            terms |= _content_terms(v)
    if not terms:
        return {"score": 1.0, "unsupported": []}
    # Accept simple inflection differences (plural/-ing/-ed) via a shared 5-char stem.
    stems = {s[:5] for s in source if len(s) >= 5}
    missing = sorted(t for t in terms if t not in source and t[:5] not in stems)
    return {
        "score": round(1.0 - len(missing) / len(terms), 3),
        "unsupported": missing[:10],
    }
