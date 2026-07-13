"""add_user_email_and_expand_username

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-19 00:07:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("idx_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("idx_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.drop_column("users", "email")
