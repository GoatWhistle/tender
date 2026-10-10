"""Точные decimal в справочнике: текстовое хранение вместо SQLite REAL."""

import sqlalchemy as sa
from alembic import op

revision = "d128fact012ab"
down_revision = "c7e5cf6c0272"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Существующие REAL сохраняются в доступной им точности. Для восстановления
    # исходных цифр старого каталога нужна повторная синхронизация XML.
    with op.batch_alter_table("allowed_values") as batch:
        for name in ("concrete", "min", "max"):
            batch.alter_column(name, existing_type=sa.Float(), type_=sa.String())


def downgrade() -> None:
    with op.batch_alter_table("allowed_values") as batch:
        for name in ("concrete", "min", "max"):
            batch.alter_column(name, existing_type=sa.String(), type_=sa.Float())
