"""catalog

Revision ID: 9e6c609fbccb
Revises:
Create Date: 2026-10-09 20:05:20.635449

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e6c609fbccb"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("okpd2", sa.String(length=32), nullable=False),
        sa.Column("okpd2_name", sa.String(), nullable=False),
        sa.Column("is_template", sa.Boolean(), nullable=False),
        sa.Column("parent", sa.String(length=64), nullable=True),
        sa.Column("units", sa.JSON(), nullable=False),
        sa.Column("rubrics", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_positions")),
    )
    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_positions_category"), ["category"], unique=False)

    op.create_table(
        "position_characteristics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("position_code", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("quantitative", sa.Boolean(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("multi", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["position_code"],
            ["positions.code"],
            name=op.f("fk_position_characteristics_position_code_positions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_characteristics")),
    )
    with op.batch_alter_table("position_characteristics", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_position_characteristics_position_code"), ["position_code"], unique=False
        )

    op.create_table(
        "allowed_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("characteristic_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("text", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("unit_code", sa.String(length=16), nullable=True),
        sa.Column("concrete", sa.Float(), nullable=True),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("min_op", sa.String(length=16), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("max_op", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["characteristic_id"],
            ["position_characteristics.id"],
            name=op.f("fk_allowed_values_characteristic_id_position_characteristics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allowed_values")),
    )
    with op.batch_alter_table("allowed_values", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_allowed_values_characteristic_id"), ["characteristic_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("allowed_values", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_allowed_values_characteristic_id"))

    op.drop_table("allowed_values")
    with op.batch_alter_table("position_characteristics", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_position_characteristics_position_code"))

    op.drop_table("position_characteristics")
    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_positions_category"))

    op.drop_table("positions")
