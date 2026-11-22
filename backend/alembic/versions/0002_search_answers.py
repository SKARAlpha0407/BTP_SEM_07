"""Store complete /search answers per exact topic

Revision ID: 0002_search_answers
Revises: 0001_initial
Create Date: 2026-11-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_search_answers"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_answers",
        # Casefolded, whitespace-collapsed topic.
        sa.Column("topic_key", sa.Text(), primary_key=True),
        sa.Column("max_results", sa.Integer(), primary_key=True),
        # Embedding model, LLM and hybrid setting: a change makes old answers unusable.
        sa.Column("config_key", sa.Text(), primary_key=True),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("search_answers_created_at_idx", "search_answers", ["created_at"])


def downgrade() -> None:
    op.drop_index("search_answers_created_at_idx", table_name="search_answers")
    op.drop_table("search_answers")
