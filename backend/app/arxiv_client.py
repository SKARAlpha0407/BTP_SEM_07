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

    query = _build_query(topic)
    is_title_query = query.startswith('ti:"')

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: List[Paper] = []
    for result in client.results(search):
        title = result.title.replace("\n", " ").strip()
        abstract = result.summary.replace("\n", " ").strip()
        arxiv_id = result.entry_id.split("/")[-1]

        papers.append(
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

    # When the user quoted an exact title, prefer papers whose title
    # matches it word-for-word (case/punctuation insensitive). If any
    # exist, return only those and drop the fanfic variants.
    if is_title_query:
        wanted = _normalize(query[4:-1])
        exact = [p for p in papers if _normalize(p.title) == wanted]
        others = [p for p in papers if _normalize(p.title) != wanted]
        papers = exact + others

    return papers


def _normalize(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()