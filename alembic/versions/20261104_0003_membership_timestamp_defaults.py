"""Add database defaults to chat membership timestamps."""

from alembic import op
import sqlalchemy as sa


revision = "20261104_0003"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "chat_memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
    )
    op.alter_column(
        "chat_memberships",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "chat_memberships",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "chat_memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
