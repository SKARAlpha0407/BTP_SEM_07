import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load from backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")


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


def extract_insights_batch(papers):
    """
    Extracts insights for a batch of papers in a single LLM call.
    Returns: List of insights, aligned 1:1 with the papers list by position.
    """
    if not api_key:
        return [{"error": "GROQ_API_KEY missing"}] * len(papers)

    if not papers:
        return []

    papers_text = ""
    for idx, paper in enumerate(papers):
        title = paper.get('title', 'N/A')
        content = paper.get('content') or paper.get('abstract', 'N/A')
        papers_text += f"--- Paper {idx} ---\nTitle: {title}\nContent: {content}\n\n"

    prompt = (
        "You are a research assistant. Extract key insights from the following papers. "
        "Respond with a JSON object with a single key 'papers' whose value is an array "
        "with exactly one element per input paper, in the same order. "
        "Each element must have: 'index' (int, the paper's position), 'tldr' (string), "
        "'problem' (string), 'methods' (string), and 'benchmarks' (string). "
        "If information is missing, use 'N/A'.\n\n"
        f"{papers_text}"
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You output JSON objects containing a 'papers' array."},
                {"role": "user", "content": prompt},
            ],
            model=MODEL,
            response_format={"type": "json_object"},
            extra_body={"reasoning_effort": "low", "max_completion_tokens": 4096},
        )

        data = json.loads(chat_completion.choices[0].message.content)

        # Normalize: accept {"papers":[...]}, any single-list object, or index-keyed objects
        if isinstance(data, dict):
            list_val = next((v for v in data.values() if isinstance(v, list)), None)
            if list_val is not None:
                data = list_val
            else:
                data = [
                    data[k]
                    for k in sorted(
                        data.keys(),
                        key=lambda k: int(k) if str(k).isdigit() else 10**9,
                    )
                ]

        if not isinstance(data, list):
            data = []

        # Align insights to papers by declared 'index', falling back to order
        aligned = [None] * len(papers)
        for i, item in enumerate(data):
            pos = (
                item.get('index')
                if isinstance(item, dict) and isinstance(item.get('index'), int)
                else i
            )
            if isinstance(pos, int) and 0 <= pos < len(papers):
                aligned[pos] = item

        return [
            it if it is not None else
            {"tldr": "N/A", "problem": "N/A", "methods": "N/A", "benchmarks": "N/A"}
            for it in aligned
        ]

    except Exception as e:
        print(f"Error during Groq batch extraction: {e}")
        return [
            {"index": i, "tldr": "Error", "problem": "Error",
             "methods": "Error", "benchmarks": "Error"}
            for i in range(len(papers))
        ]


def synthesize_results(papers_summaries):
    if not api_key:
        return "Synthesis blocked: GROQ_API_KEY missing"

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
        return completion.choices[0].message.content
    except Exception as e:
        return f"Synthesis Error: {str(e)}"


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

        return _sanitize_labels(json.loads(content))

    except json.JSONDecodeError as e:
        print(f"Cluster labeling: JSON parse failed — {e}")
        return {}
    except Exception as e:
        print(f"Error during Groq cluster labeling: {e}")
        return {}