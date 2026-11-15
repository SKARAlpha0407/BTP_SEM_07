"""Write-only DB helpers for caching pipeline results."""
import logging
import datetime
from typing import List

from .db.connection import SessionLocal
from .db.repository import upsert_paper, upsert_embedding, upsert_insight, get_papers_by_ids
from .arxiv_client import Paper

logger = logging.getLogger(__name__)


def save_papers_and_embeddings(
    papers: List[Paper],
    embeddings: List[List[float]],
    model_name: str,
) -> None:
    """Save papers and their embeddings to the database."""
    session = SessionLocal()
    try:
        for paper, vec in zip(papers, embeddings):
            published = paper.published
            if isinstance(published, str):
                published = datetime.date.fromisoformat(published[:10])
            data = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "categories": paper.categories,
                "published": published,
                "arxiv_url": paper.arxiv_url,
                "pdf_url": paper.pdf_url,
            }
            upsert_paper(session, data)
            upsert_embedding(session, paper.arxiv_id, model_name, vec)
        session.commit()
    except Exception:
        session.rollback()
        logger.error("Failed to save papers and embeddings", exc_info=True)
    finally:
        session.close()


def save_insights(
    pairs: List[tuple[str, dict]],
    llm_model: str,
) -> None:
    """Save LLM insights to the database."""
    session = SessionLocal()
    try:
        for arxiv_id, insight in pairs:
            upsert_insight(session, arxiv_id, llm_model, insight)
        session.commit()
    except Exception:
        session.rollback()
        logger.error("Failed to save insights", exc_info=True)
    finally:
        session.close()


def load_paper_objects(
    session,
    arxiv_ids: list[str],
) -> list:
    """Load Paper objects for given arxiv_ids preserving input order."""
    if not arxiv_ids:
        return []
    rows = get_papers_by_ids(session, arxiv_ids)
    row_map = {row["arxiv_id"]: row for row in rows}
    papers = []
    for arxiv_id in arxiv_ids:
        row = row_map.get(arxiv_id)
        if row:
            papers.append(
                Paper(
                    title=row["title"],
                    authors=row["authors"] or [],
                    abstract=row["abstract"],
                    arxiv_id=row["arxiv_id"],
                    arxiv_url=row["arxiv_url"] or "",
                    pdf_url=row["pdf_url"] or "",
                    published=row["published"] or "",
                    categories=row["categories"] or [],
                )
            )
    return papers