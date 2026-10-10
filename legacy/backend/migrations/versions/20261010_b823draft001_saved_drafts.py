"""Сохранённые черновики и неотправленный текст, отдельно от ревизий анализа."""

import sqlalchemy as sa
from alembic import op

revision = "b823draft001"
down_revision = "d128fact012ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_drafts",
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("analysis_sessions.id"), primary_key=True
        ),
        sa.Column("saved_revision", sa.Integer(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("saved_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("saved_drafts")
