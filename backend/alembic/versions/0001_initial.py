"""Initial migration

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "papers",
        sa.Column("arxiv_id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.ARRAY(sa.Text())),
        sa.Column("categories", postgresql.ARRAY(sa.Text())),
        sa.Column("published", sa.Date()),
        sa.Column("arxiv_url", sa.Text()),
        sa.Column("pdf_url", sa.Text()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "paper_embeddings",
        sa.Column("arxiv_id", sa.Text(), sa.ForeignKey("papers.arxiv_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "paper_insights",
        sa.Column("arxiv_id", sa.Text(), sa.ForeignKey("papers.arxiv_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("llm_model", sa.Text(), primary_key=True),
        sa.Column("tldr", sa.Text()),
        sa.Column("problem", sa.Text()),
        sa.Column("methods", sa.Text()),
        sa.Column("benchmarks", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.execute(
        "CREATE INDEX paper_embeddings_hnsw_idx "
        "ON paper_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("paper_insights")
    op.drop_table("paper_embeddings")
    op.drop_table("papers")