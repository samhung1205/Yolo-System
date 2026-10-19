"""unique turn_index per user conversation in chat_logs

Two requests to the same conversation at once (double-click, two tabs) could
both read the same "next" turn_index and store duplicate turns. This adds a
unique constraint on (user_id, conversation_id, turn_index); the repository
retries with the next index when an insert hits it.

Existing duplicates are renumbered first: each conversation's turns become
1..n in their current order (turn_index, created_at, id). Turn order is all
turn_index is used for, so nothing else changes.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-20 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "uq_chat_logs_user_conversation_turn"


def _renumber_turns(bind) -> int:
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, conversation_id, turn_index FROM chat_logs "
            "ORDER BY user_id, conversation_id, turn_index, created_at, id"
        )
    ).fetchall()
    updates = []
    current_key = None
    position = 0
    for row_id, user_id, conversation_id, turn_index in rows:
        key = (user_id, conversation_id)
        position = position + 1 if key == current_key else 1
        current_key = key
        if turn_index != position:
            updates.append({"id": row_id, "turn_index": position})
    if updates:
        bind.execute(sa.text("UPDATE chat_logs SET turn_index = :turn_index WHERE id = :id"), updates)
    return len(updates)


def upgrade() -> None:
    _renumber_turns(op.get_bind())
    op.create_unique_constraint(CONSTRAINT_NAME, "chat_logs", ["user_id", "conversation_id", "turn_index"])


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "chat_logs", type_="unique")
