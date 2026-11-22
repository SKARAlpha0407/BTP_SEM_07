import os
import re
import json
import logging
import traceback
from groq import Groq
from dotenv import load_dotenv

# Load from backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key, timeout=60.0) if api_key else None
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
logger = logging.getLogger(__name__)

# Papers per insight call. Larger batches risk running out of completion tokens
# (the reasoning model counts its reasoning against the same limit).
INSIGHT_BATCH_SIZE = int(os.environ.get("INSIGHT_BATCH_SIZE", "8"))
_INSIGHT_FIELDS = ("tldr", "problem", "methods", "benchmarks")
_PLACEHOLDERS = {"", "N/A", "NA", "ERROR"}


def _extract_tldr(summary) -> str:
    """
    Paper.summary can be either:
      - a str  (raw summary text from arxiv_client),
      - a dict (post-extract_insights_batch, shape {"tldr": ..., "problem": ...}).
    Return the best TL;DR string we can, or "" if none.
    """
    if isinstance(summary, str):
        return summary
    if isinstance(summary, dict):
        return summary.get("tldr") or summary.get("summary") or ""
    return ""


def _empty_insight(idx: int = -1) -> dict:
    return {
        "index": idx,
        "tldr": "N/A",
        "problem": "N/A",
        "methods": "N/A",
        "benchmarks": "N/A",
    }


def _error_insight(idx: int = -1) -> dict:
    return {"index": idx, "tldr": "Error", "problem": "Error",
            "methods": "Error", "benchmarks": "Error"}


def is_placeholder_insight(insight) -> bool:
    """True when an insight carries no real content (all fields N/A, Error or empty).

    Such insights are never cached, and cached ones are treated as misses."""
    if not isinstance(insight, dict):
        return True
    return all(
        str(insight.get(f) or "").strip().upper() in _PLACEHOLDERS
        for f in _INSIGHT_FIELDS
    )


def _clean_insight(item: dict, idx: int) -> dict:
    out = {"index": idx}
    for f in _INSIGHT_FIELDS:
        v = item.get(f)
        if isinstance(v, (list, tuple)):
            v = "; ".join(str(x) for x in v)
        out[f] = str(v).strip() if v is not None and str(v).strip() else "N/A"
    return out


_HEX = set("0123456789abcdefABCDEF")


def _repair_backslashes(s: str) -> str:
    r"""Escape backslashes that are not meant as JSON escapes.

    LLMs often copy LaTeX from abstracts without escaping it. A raw \beta is
    valid JSON (backspace + 'eta'), and \uparrow is invalid JSON, so both must
    be repaired. Rules, applied left to right:
      \\  \"  \/          kept (already valid escapes)
      \uXXXX              kept when four hex digits follow
      \b \f \r \t + letter, \n + lowercase letter
                          treated as a LaTeX command (\beta, \frac, \rho, \theta, \nabla)
      \n, \t, \r, \b, \f otherwise   kept as JSON escapes
      anything else       the backslash is escaped (\alpha, \mathbf, \uparrow)
    """
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = s[i + 1] if i + 1 < n else ""
        after = s[i + 2] if i + 2 < n else ""
        if nxt in ('\\', '"', '/'):
            out.append(c + nxt)
            i += 2
        elif nxt == "u" and len(s) >= i + 6 and all(h in _HEX for h in s[i + 2:i + 6]):
            out.append(s[i:i + 6])
            i += 6
        elif nxt in "bfrt" and after.isalpha():
            out.append("\\\\")
            i += 1
        elif nxt == "n" and after.isalpha() and after.islower():
            out.append("\\\\")
            i += 1
        elif nxt in "bfnrt":
            out.append(c + nxt)
            i += 2
        else:
            out.append("\\\\")
            i += 1
    return "".join(out)


def _outermost_json(s: str) -> str:
    """The text from the first { or [ to the matching last } or ], if any."""
    starts = [i for i in (s.find("{"), s.find("[")) if i != -1]
    if not starts:
        return s
    start = min(starts)
    end = max(s.rfind("}"), s.rfind("]"))
    return s[start:end + 1] if end > start else s


def _safe_json_loads(text: str):
    """Parse JSON from an LLM response, tolerating LaTeX backslashes and stray prose."""
    if not text:
        raise ValueError("empty content")
    s = text.strip()
    # Strip markdown fences if present
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    s = _outermost_json(s)
    return json.loads(_repair_backslashes(s))


def _align(data, n: int):
    """Map parsed model output onto n papers. Returns a list of n items or None."""
    if isinstance(data, dict):
        papers = data.get("papers")
        if isinstance(papers, list):
            data = papers
        else:
            list_val = next((v for v in data.values() if isinstance(v, list)), None)
            if list_val is not None:
                data = list_val
            elif all(str(k).isdigit() for k in data):
                data = [data[k] for k in sorted(data, key=lambda k: int(k))]
            else:
                return None
    if not isinstance(data, list):
        return None
    items = [it for it in data if isinstance(it, dict)]
    if len(items) == n:
        # Same length as the input: the prompt asks for input order.
        return items
    declared = [it.get("index") for it in items]
    if (
        all(isinstance(d, int) and 0 <= d < n for d in declared)
        and len(set(declared)) == len(declared)
    ):
        aligned = [None] * n
        for it in items:
            aligned[it["index"]] = it
        return aligned
    return None


def _extract_chunk(papers, offset: int):
    papers_text = ""
    for idx, paper in enumerate(papers):
        title = paper.get('title', 'N/A')
        content = paper.get('content') or paper.get('abstract', 'N/A')
        papers_text += f"--- Paper {idx} ---\nTitle: {title}\nContent: {content}\n\n"

    prompt = (
        "You are a research assistant. Extract key insights from the following papers. "
        "Respond with a JSON object with a single key 'papers' whose value is an array "
        "with exactly one element per input paper, in the same order. "
        "Each element must have: 'index' (int, the paper's position, starting at 0), "
        "'tldr' (string), 'problem' (string), 'methods' (string), and 'benchmarks' (string). "
        "If information is missing, use 'N/A'.\n\n"
        f"{papers_text}"
    )
    n = len(papers)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You output JSON objects containing a 'papers' array."},
                {"role": "user", "content": prompt},
            ],
            model=MODEL,
            extra_body={"reasoning_effort": "low", "max_completion_tokens": 4096},
        )
        choice = chat_completion.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            logger.warning("insight batch hit the completion-token limit (%d papers)", n)
            return [_error_insight(offset + i) for i in range(n)]
        content = (choice.message.content or "").strip()
        if not content:
            logger.warning("insight batch: model returned empty content")
            return [_error_insight(offset + i) for i in range(n)]

        aligned = _align(_safe_json_loads(content), n)
        if aligned is None:
            logger.warning("insight batch: could not align %d items to papers", n)
            return [_error_insight(offset + i) for i in range(n)]
        return [
            _clean_insight(it, offset + i) if isinstance(it, dict) else _empty_insight(offset + i)
            for i, it in enumerate(aligned)
        ]
    except Exception:
        logger.exception("insight batch failed")
        return [_error_insight(offset + i) for i in range(n)]


def extract_insights_batch(papers):
    """
    Extracts insights for papers, INSIGHT_BATCH_SIZE papers per LLM call.
    Returns: List of insights, aligned 1:1 with the papers list by position.
    A failed or unparseable call yields 'Error' placeholders for that chunk
    only; callers must not cache placeholders (see is_placeholder_insight).

    NOTE: does NOT use response_format=json_object. Same reason as
    get_cluster_labels below — the gpt-oss reasoning model sometimes emits
    nothing in the content channel under strict JSON mode, which Groq surfaces
    as `json_validate_failed` with empty failed_generation. We parse manually
    instead.
    """
    if not papers:
        return []
    if not client:
        return [_error_insight(i) for i in range(len(papers))]

    out = []
    size = max(1, INSIGHT_BATCH_SIZE)
    for start in range(0, len(papers), size):
        out.extend(_extract_chunk(papers[start:start + size], start))
    return out


SYNTHESIS_UNAVAILABLE = "A synthesis could not be written right now. The individual papers are listed on the left."


def synthesize_results(papers_summaries):
    if not client:
        return SYNTHESIS_UNAVAILABLE

    summary_text = "\n".join(
        f"Paper: {p.get('title', 'Unknown')}\n"
        f"Summary: {_extract_tldr(p.get('summary'))}"
        for p in papers_summaries
    )
    prompt = (
        "Based on the following research paper summaries, write a cohesive "
        "cross-paper synthesis paragraph:\n\n"
        f"{summary_text}"
    )

    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL,
            extra_body={"reasoning_effort": "low"},
        )
        return (completion.choices[0].message.content or "").strip() or SYNTHESIS_UNAVAILABLE
    except Exception:
        logger.exception("synthesis failed")
        return SYNTHESIS_UNAVAILABLE


def _sanitize_labels(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v).strip()[:80] for k, v in raw.items() if str(v).strip()}


def get_cluster_labels(clusters, topic: str = "") -> dict:
    """
    Labels clusters in ONE batched Groq call.
    clusters: {cid: [texts]}, {cid: text}, or a list of either.
    Returns: {cid_str: label}. ALWAYS a dict — {} on any failure,
    so main.py's invariant guard fills gaps with 'Cluster {cid}'.

    NOTE: does NOT use response_format=json_object. The gpt-oss reasoning model
    sometimes emits nothing in the content channel under strict JSON mode,
    which Groq surfaces as `json_validate_failed` with empty failed_generation.
    We parse manually with a markdown-fence stripper instead.
    """
    if not client:
        print("Cluster labeling skipped: GROQ_API_KEY missing")
        return {}
    if not clusters:
        return {}

    try:
        pairs = clusters.items() if isinstance(clusters, dict) else enumerate(clusters)
        items = []
        for cid, texts in pairs:
            blob = (
                " | ".join(map(str, texts))
                if isinstance(texts, (list, tuple))
                else str(texts)
            )
            items.append(f"Cluster {cid}: {blob[:400]}")

        prompt = (
            f"Topic: {topic}\n\n"
            "Below are clusters of research paper titles/abstracts. For each cluster, "
            "produce a concise research-theme label (2-5 words).\n\n"
            + "\n".join(items)
            + "\n\nReturn ONLY a JSON object mapping cluster numbers (as strings) "
            "to labels. Do not include any prose, explanation, or markdown code "
            'fences. Example format: {"0": "Graph Embeddings", "1": "Attention"}'
        )

        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL,
            extra_body={"reasoning_effort": "low", "max_completion_tokens": 4096},
        )

        content = (completion.choices[0].message.content or "").strip()
        if not content:
            print("Cluster labeling: model returned empty content")
            return {}

        # Strip markdown fences if the model added them despite instructions
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        return _sanitize_labels(_safe_json_loads(content))

    except json.JSONDecodeError as e:
        print(f"Cluster labeling: JSON parse failed — {e}")
        return {}
    except Exception as e:
        print(f"Error during Groq cluster labeling: {e}")
        return {}