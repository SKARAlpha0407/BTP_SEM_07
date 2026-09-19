
import arxiv
from dataclasses import dataclass, field
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

def search_papers(topic: str, max_results: int = 30) -> List[Paper]:
    client = arxiv.Client()
    # Use "all:" prefix for a broad search across title, abstract, and authors
    search = arxiv.Search(
        query=f"all:{topic}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    papers = []
    for result in client.results(search):
        # Clean titles and abstracts
        title = result.title.replace('\n', ' ').strip()
        abstract = result.summary.replace('\n', ' ').strip()
        
        # Parse arxiv_id from entry_id (e.g., http://arxiv.org/abs/2301.00000 -> 2301.00000)
        arxiv_id = result.entry_id.split('/')[-1]
        
        papers.append(Paper(
            title=title,
            authors=[author.name for author in result.authors],
            abstract=abstract,
            arxiv_id=arxiv_id,
            arxiv_url=result.entry_id,
            pdf_url=result.pdf_url,
            published=result.published.strftime('%Y-%m-%d'),
            categories=result.categories
        ))
    
    return papers
