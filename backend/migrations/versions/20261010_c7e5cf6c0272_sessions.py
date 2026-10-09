"""Сессии анализа, сообщения и снимки ревизий

Revision ID: c7e5cf6c0272
Revises: c47db98316ab
Create Date: 2026-10-10 02:37:07.052905

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e5cf6c0272"
down_revision: str | Sequence[str] | None = "c47db98316ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_sessions")),
    )
    op.create_table(
        "session_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["analysis_sessions.id"],
            name=op.f("fk_session_messages_session_id_analysis_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_messages")),
        sa.UniqueConstraint("session_id", "revision", name=op.f("uq_session_messages_session_id")),
    )
    op.create_table(
        "session_revisions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("request_text", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["analysis_sessions.id"],
            name=op.f("fk_session_revisions_session_id_analysis_sessions"),
        ),
        sa.PrimaryKeyConstraint("session_id", "revision", name=op.f("pk_session_revisions")),
        sa.UniqueConstraint(
            "session_id", "idempotency_key", name=op.f("uq_session_revisions_session_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("session_revisions")
    op.drop_table("session_messages")
    op.drop_table("analysis_sessions")
