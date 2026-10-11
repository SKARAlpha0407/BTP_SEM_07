import json
"""Repository layer for paper data operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Paper, PaperEmbedding, PaperInsight


def upsert_paper(session: Session, data: dict) -> None:
    stmt = pg_insert(Paper).values(
        arxiv_id=data["arxiv_id"],
        title=data["title"],
        abstract=data["abstract"],
        authors=data.get("authors") or [],
        categories=data.get("categories") or [],
        published=data["published"],
        arxiv_url=data["arxiv_url"],
        pdf_url=data["pdf_url"],
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["arxiv_id"],
        set_={
            "title": stmt.excluded.title,
            "abstract": stmt.excluded.abstract,
            "authors": stmt.excluded.authors,
            "categories": stmt.excluded.categories,
            "published": stmt.excluded.published,
            "arxiv_url": stmt.excluded.arxiv_url,
            "pdf_url": stmt.excluded.pdf_url,
            "fetched_at": func.now(),
        },
    )
    session.execute(stmt)


def upsert_embedding(session: Session, arxiv_id: str, model_name: str, embedding: list[float]) -> None:
    stmt = pg_insert(PaperEmbedding).values(
        arxiv_id=arxiv_id,
        model_name=model_name,
        embedding=embedding,
        created_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["arxiv_id"],
        set_={
            "model_name": stmt.excluded.model_name,
            "embedding": stmt.excluded.embedding,
            "created_at": stmt.excluded.created_at,
        },
    )
    session.execute(stmt)


def upsert_insight(session: Session, arxiv_id: str, llm_model: str, insight: dict) -> None:
    stmt = pg_insert(PaperInsight).values(
        arxiv_id=arxiv_id,
        llm_model=llm_model,
        tldr=insight.get("tldr"),
        problem=insight.get("problem"),
        methods=insight.get("methods"),
        benchmarks=insight.get("benchmarks"),
        created_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["arxiv_id", "llm_model"],
        set_={
            "tldr": stmt.excluded.tldr,
            "problem": stmt.excluded.problem,
            "methods": stmt.excluded.methods,
            "benchmarks": stmt.excluded.benchmarks,
            "created_at": stmt.excluded.created_at,
        },
    )
    session.execute(stmt)


def get_missing_embeddings(session: Session, arxiv_ids: list[str], model_name: str) -> list[str]:
    if not arxiv_ids:
        return []
    placeholders = ",".join([f":id{i}" for i in range(len(arxiv_ids))])
    params: dict[str, Any] = {f"id{i}": arxiv_id for i, arxiv_id in enumerate(arxiv_ids)}
    params["model_name"] = model_name
    sql = text(
        f"""
        SELECT arxiv_id FROM paper_embeddings
        WHERE arxiv_id IN ({placeholders}) AND model_name = :model_name
        """
    )
    result = session.execute(sql, params)
    existing = {row[0] for row in result}
    return [aid for aid in arxiv_ids if aid not in existing]


def search_similar(session: Session, query_vec: list[float], top_k: int = 20) -> list[tuple[str, float]]:
    sql = text(
        """
        SELECT arxiv_id, 1 - (embedding <=> CAST(:vec AS vector)) AS score
        FROM paper_embeddings
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :k
        """
    )
    result = session.execute(sql, {"vec": query_vec, "k": top_k})
    return [(row[0], float(row[1])) for row in result]


def search_similar_with_ttl(
    session: Session,
    query_vec: list[float],
    top_k: int = 20,
    max_age_hours: int = 12,
) -> list[tuple[str, float]]:
    """ANN search with time-to-live filter on papers.fetched_at."""
    sql = text(
        """
        SELECT e.arxiv_id, 1 - (e.embedding <=> CAST(:vec AS vector)) AS score
        FROM paper_embeddings e
        JOIN papers p ON p.arxiv_id = e.arxiv_id
        WHERE p.fetched_at > NOW() - (INTERVAL '1 hour' * :age)
        ORDER BY e.embedding <=> CAST(:vec AS vector)
        LIMIT :k
        """
    )
    result = session.execute(sql, {"vec": query_vec, "k": top_k, "age": max_age_hours})
    return [(row[0], float(row[1])) for row in result]


def get_papers_by_ids(session: Session, arxiv_ids: list[str]) -> list[dict]:
    """Fetch paper metadata for a list of arxiv_ids."""
    if not arxiv_ids:
        return []
    sql = text(
        """
        SELECT arxiv_id, title, abstract, authors, categories,
               published, arxiv_url, pdf_url
        FROM papers
        WHERE arxiv_id = ANY(:ids)
        """
    )
    result = session.execute(sql, {"ids": arxiv_ids})
    rows = result.fetchall()
    return [
        {
            "arxiv_id": row[0],
            "title": row[1],
            "abstract": row[2],
            "authors": row[3],
            "categories": row[4],
            "published": row[5].isoformat() if row[5] else None,
            "arxiv_url": row[6],
            "pdf_url": row[7],
        }
        for row in rows
    ]


def get_cached_insights(
    session: Session,
    arxiv_ids: list[str],
    llm_model: str,
) -> dict[str, dict]:
    """Fetch cached insights for a list of arxiv_ids and model."""
    if not arxiv_ids:
        return {}
    sql = text(
        """
        SELECT arxiv_id, tldr, problem, methods, benchmarks
        FROM paper_insights
        WHERE llm_model = :model AND arxiv_id = ANY(:ids)
        """
    )
    result = session.execute(sql, {"model": llm_model, "ids": arxiv_ids})
    return {
        row[0]: {
            "tldr": row[1],
            "problem": row[2],
            "methods": row[3],
            "benchmarks": row[4],
        }
        for row in result
    }


def get_embeddings_for_ids(
    session: Session,
    arxiv_ids: list[str],
    model_name: str,
) -> dict[str, list[float]]:
    """Fetch embeddings for given arxiv_ids and model."""
    if not arxiv_ids:
        return {}
    sql = text(
        """
        SELECT arxiv_id, embedding FROM paper_embeddings
        WHERE model_name = :model AND arxiv_id = ANY(:ids)
        """
    )
    result = session.execute(sql, {"model": model_name, "ids": arxiv_ids})
    def _to_list(v):
        if isinstance(v, str):
            return [float(x) for x in json.loads(v)]
        return [float(x) for x in v]
    return {row[0]: _to_list(row[1]) for row in result}
