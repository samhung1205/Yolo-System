"""add_chat_conversation_fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-19 11:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_logs", sa.Column("conversation_id", sa.String(length=64), nullable=True))
    op.add_column("chat_logs", sa.Column("turn_index", sa.Integer(), nullable=True))

    op.execute("UPDATE chat_logs SET conversation_id = CAST(id AS CHAR(64)) WHERE conversation_id IS NULL")
    op.execute("UPDATE chat_logs SET turn_index = 1 WHERE turn_index IS NULL")

    op.alter_column("chat_logs", "conversation_id", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("chat_logs", "turn_index", existing_type=sa.Integer(), nullable=False)
    op.create_index("ix_chat_logs_conversation_id", "chat_logs", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_logs_conversation_id", table_name="chat_logs")
    op.drop_column("chat_logs", "turn_index")
    op.drop_column("chat_logs", "conversation_id")
