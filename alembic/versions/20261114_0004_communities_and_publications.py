"""Add logical communities and per-chat game publications.

Revision ID: 20261114_0004
Revises: 20261104_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_0004"
down_revision = "20261104_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "communities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("chat_spaces", sa.Column("community_id", sa.Integer(), nullable=True))
    conn = op.get_bind()
    chats = conn.execute(sa.text("SELECT id, title FROM chat_spaces")).all()
    for chat_id, title in chats:
        community_id = conn.execute(
            sa.text("INSERT INTO communities (title) VALUES (:title) RETURNING id"),
            {"title": title},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE chat_spaces SET community_id = :community_id WHERE id = :id"),
            {"community_id": community_id, "id": chat_id},
        )
    with op.batch_alter_table("chat_spaces") as batch:
        batch.alter_column("community_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_chat_spaces_community_id_communities", "communities", ["community_id"], ["id"], ondelete="CASCADE")

    op.create_table(
        "game_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_id"], ["chat_spaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chat_id", "message_id", name="uq_game_publications_chat_message"),
        sa.UniqueConstraint("game_id", "chat_id", name="uq_game_publications_game_chat"),
    )
    conn.execute(sa.text(
        "INSERT INTO game_publications (game_id, chat_id, message_id) "
        "SELECT id, chat_id, source_message_id FROM games WHERE source_message_id IS NOT NULL"
    ))


def downgrade() -> None:
    op.drop_table("game_publications")
    with op.batch_alter_table("chat_spaces") as batch:
        batch.drop_constraint("fk_chat_spaces_community_id_communities", type_="foreignkey")
        batch.drop_column("community_id")
    op.drop_table("communities")
