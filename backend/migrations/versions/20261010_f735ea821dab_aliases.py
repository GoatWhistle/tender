"""aliases

Revision ID: f735ea821dab
Revises: a42dc73c0675
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f735ea821dab"
down_revision: str | Sequence[str] | None = "a42dc73c0675"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aliases",
        sa.Column("group_code", sa.String(), nullable=False),
        sa.Column("alias", sa.String(512), nullable=False),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["group_code"], ["positions.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_code", "alias"),
    )


def downgrade() -> None:
    op.drop_table("aliases")
