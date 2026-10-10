"""Сохранённые поисковые документы, векторы и метаданные.

Revision ID: c47db98316ab
Revises: f735ea821dab
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c47db98316ab"
down_revision: str | Sequence[str] | None = "f735ea821dab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_vector_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("recipe", sa.String(), nullable=False),
        sa.Column("normalization", sa.String(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "group_search_vectors",
        sa.Column("group_code", sa.String(64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["group_code"], ["positions.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_code", "ordinal"),
    )


def downgrade() -> None:
    op.drop_table("group_search_vectors")
    op.drop_table("search_vector_metadata")
