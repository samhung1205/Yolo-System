"""add users.token_version for access-token revocation

JWTs carry the user's ``token_version`` as the ``ver`` claim. Changing the
password, deactivating the account or changing the admin flag bumps the
version, so every token issued before that change stops being accepted.
Tokens issued before this migration have no ``ver`` claim and are treated as
version 0, so existing sessions keep working until the next such change.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-20 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
