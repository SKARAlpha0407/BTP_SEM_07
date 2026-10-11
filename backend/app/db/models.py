from datetime import date, datetime
from typing import List

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Paper(Base):
    __tablename__ = "papers"

    arxiv_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    categories: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    published: Mapped[date] = mapped_column(Date, nullable=False)
    arxiv_url: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaperEmbedding(Base):
    __tablename__ = "paper_embeddings"

    arxiv_id: Mapped[str] = mapped_column(
        Text, ForeignKey("papers.arxiv_id", ondelete="CASCADE"), primary_key=True
    )
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaperInsight(Base):
    __tablename__ = "paper_insights"

    arxiv_id: Mapped[str] = mapped_column(
        Text, ForeignKey("papers.arxiv_id", ondelete="CASCADE"), primary_key=True
    )
    llm_model: Mapped[str] = mapped_column(Text, primary_key=True)
    tldr: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    methods: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
