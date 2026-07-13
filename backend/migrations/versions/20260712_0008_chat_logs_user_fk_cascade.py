"""chat_logs_user_fk_cascade

Recreate the chat_logs.user_id foreign key with ON DELETE CASCADE so that
deleting a user (admin flow) no longer fails with a FK violation when the
user has chat / agent history.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12 17:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_chat_logs_user_id_users"


def _existing_user_fk_name() -> str | None:
    """The original FK was created without an explicit name (MySQL auto-names
    it e.g. ``chat_logs_ibfk_1``), so look it up via the inspector."""
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("chat_logs"):
        if fk.get("referred_table") == "users" and fk.get("constrained_columns") == ["user_id"]:
            return fk.get("name")
    return None


def upgrade() -> None:
    existing = _existing_user_fk_name()
    if existing:
        op.drop_constraint(existing, "chat_logs", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "chat_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    existing = _existing_user_fk_name()
    if existing:
        op.drop_constraint(existing, "chat_logs", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "chat_logs",
        "users",
        ["user_id"],
        ["id"],
    )
