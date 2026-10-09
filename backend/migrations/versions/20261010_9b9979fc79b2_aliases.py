"""aliases

Словарь синонимов групп КТРУ из `data/aliases.csv`; заполняет синхронизация справочника.

Revision ID: 9b9979fc79b2
Revises: a42dc73c0675
Create Date: 2026-10-09 22:54:35.859068

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b9979fc79b2"
down_revision: str | Sequence[str] | None = "a42dc73c0675"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_code", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aliases")),
    )
    with op.batch_alter_table("aliases", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_aliases_group_code"), ["group_code"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("aliases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_aliases_group_code"))

    op.drop_table("aliases")
