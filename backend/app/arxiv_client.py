import re

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


def _escape(topic: str) -> str:
    """Make user text safe inside an arXiv query: drop quotes, parentheses and
    field-prefix colons so input cannot alter the query structure."""
    cleaned = re.sub(r'["()\\:]+', " ", topic)
    return re.sub(r"\s+", " ", cleaned).strip()


# One shared client: arXiv asks for <= 1 request every 3 seconds. The client
# enforces the delay between calls and retries transient 5xx / empty pages.
_client = arxiv.Client(page_size=50, delay_seconds=3.0, num_retries=3)


def search_papers(topic: str, max_results: int = 30) -> List[Paper]:
    client = _client
    safe = _escape(topic)
    if not safe:
        return []

    # Search both all: and ti: fields
    all_query = f"all:{safe}"
    ti_query = f'ti:"{safe}"'

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

    all_results = fetch_papers(all_query, max_results)
    ti_results = fetch_papers(ti_query, 10) # smaller limit for title matches

    # Merge and deduplicate by arxiv_id
    merged = {}
    for p in (ti_results + all_results):
        merged[p.arxiv_id] = p

    papers = list(merged.values())

    # Rank title matches first
    norm_topic = _normalize(topic)
    topic_words = [w for w in norm_topic.split() if len(w) > 3]

    def get_tier(p: Paper) -> int:
        norm_title = _normalize(p.title)
        # Exact title match
        if norm_title == norm_topic:
            return 0
        # Title contains all significant words
        if all(word in norm_title for word in topic_words) and topic_words:
            return 1
        # Everything else
        return 2

    papers.sort(key=lambda p: get_tier(p))

    return papers


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()