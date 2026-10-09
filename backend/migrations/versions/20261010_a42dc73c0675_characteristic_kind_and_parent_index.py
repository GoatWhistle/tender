"""characteristic kind and parent index

Вид характеристики `kind` вместо `multi`: `multi` выводился из `choiceType` и неверен, `kind` из
него не восстановить. Поэтому справочник очищается в обе стороны — его заново кладёт
синхронизация (`main.sync_catalog`), до неё `/health/ready` отвечает `catalog_empty`.

Revision ID: a42dc73c0675
Revises: 9e6c609fbccb
Create Date: 2026-10-10 01:14:40.608944

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a42dc73c0675"
down_revision: str | Sequence[str] | None = "9e6c609fbccb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def clear_catalog() -> None:
    for table in ("allowed_values", "position_characteristics", "positions"):
        op.execute(sa.text(f"DELETE FROM {table}"))


def upgrade() -> None:
    clear_catalog()
    with op.batch_alter_table("position_characteristics", schema=None) as batch_op:
        batch_op.add_column(sa.Column("kind", sa.String(length=16), nullable=False))
        batch_op.drop_column("multi")

    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_positions_parent"), ["parent"], unique=False)


def downgrade() -> None:
    clear_catalog()
    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_positions_parent"))

    with op.batch_alter_table("position_characteristics", schema=None) as batch_op:
        batch_op.add_column(sa.Column("multi", sa.BOOLEAN(), nullable=False))
        batch_op.drop_column("kind")
