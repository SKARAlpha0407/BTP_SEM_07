import arxiv
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Paper:
    title: str
    authors: List[str]
    abstract: str
    arxiv_id: str
    arxiv_url: str
    pdf_url: str
    published: str
    categories: List[str]
    relevance_score: Optional[float] = None
    summary: Optional[dict] = None


def _build_query(topic: str) -> str:
    """
    Build an arXiv query string.

    - If the topic is wrapped in double quotes, do an exact title search
      (ti:"..."). This catches canonical papers like "Attention Is All You
      Need" that a broad all: search would bury under 50k keyword matches.
    - Otherwise search all fields with the raw topic.
    """
    stripped = topic.strip()
    if len(stripped) >= 2 and stripped.startswith('"') and stripped.endswith('"'):
        inner = stripped[1:-1].strip()
        if inner:
            return f'ti:"{inner}"'
    return f"all:{stripped}"


def search_papers(topic: str, max_results: int = 30) -> List[Paper]:
    client = arxiv.Client()

    # 2a. DUAL SEARCH: search both all: and ti:
    all_query = f"all:{topic}"
    ti_query = f"ti:\"{topic}\""

    def fetch_papers(q: str, limit: int) -> List[Paper]:
        search = arxiv.Search(
            query=q,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for result in client.results(search):
            title = result.title.replace("\n", " ").strip()
            abstract = result.summary.replace("\n", " ").strip()
            arxiv_id = result.entry_id.split("/")[-1]
            results.append(
                Paper(
                    title=title,
                    authors=[author.name for author in result.authors],
                    abstract=abstract,
                    arxiv_id=arxiv_id,
                    arxiv_url=result.entry_id,
                    pdf_url=result.pdf_url,
                    published=result.published.strftime("%Y-%m-%d"),
                    categories=result.categories,
                )
            )
        return results

    # Fetch from both sources
    all_results = fetch_papers(all_query, max_results)
    ti_results = fetch_papers(ti_query, 10) # smaller limit for title matches

    # Merge and deduplicate by arxiv_id
    merged = {}
    for p in (ti_results + all_results):
        merged[p.arxiv_id] = p

    papers = list(merged.values())

    # 2b. TITLE-MATCH PRIORITIZATION
    norm_topic = _normalize(topic)
    topic_words = [w for w in norm_topic.split() if len(w) > 3]

    def get_tier(p: Paper) -> int:
        norm_title = _normalize(p.title)
        # Tier 1: Exact match
        if norm_title == norm_topic:
            return 0
        # Tier 2: Contains all significant words
        if all(word in norm_title for word in topic_words) and topic_words:
            return 1
        # Tier 3: Others
        return 2

    papers.sort(key=lambda p: get_tier(p))

    return papers


def _normalize(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()