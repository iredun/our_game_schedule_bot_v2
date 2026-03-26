"""rename duration to minutes

Revision ID: 20260326_0002
Revises: 20260318_0001
Create Date: 2026-03-26 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260326_0002"
down_revision: Union[str, None] = "20260318_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))

    op.execute(sa.text("UPDATE games SET duration_minutes = duration_hours * 60"))

    with op.batch_alter_table("games") as batch_op:
        batch_op.drop_column("duration_hours")
        batch_op.alter_column("duration_minutes", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.add_column(sa.Column("duration_hours", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE games "
            "SET duration_hours = CASE "
            "WHEN duration_minutes % 60 = 0 THEN duration_minutes / 60 "
            "ELSE (duration_minutes + 59) / 60 "
            "END"
        )
    )

    with op.batch_alter_table("games") as batch_op:
        batch_op.drop_column("duration_minutes")
        batch_op.alter_column("duration_hours", nullable=False)
