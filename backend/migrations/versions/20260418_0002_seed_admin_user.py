"""seed_admin_user

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-18 00:00:00.000000

Seeds an initial admin account.
Password: Admin@2026  (bcrypt hash, change immediately after first login)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pre-computed bcrypt hash of "Admin@2026"
# To regenerate: python -c "import bcrypt; print(bcrypt.hashpw(b'Admin@2026', bcrypt.gensalt()).decode())"
ADMIN_PASSWORD_HASH = "$2b$12$UiaLqzklmpGuW.lmjfbDZ.HOaLgK50SJXnQzfL8UQOqZG9P68XnnW"


def upgrade() -> None:
    # Insert default admin only if not already exists
    op.execute(
        sa.text("""
        INSERT IGNORE INTO users (username, password_hash, nickname, is_admin, is_active)
        VALUES (:username, :password_hash, :nickname, :is_admin, :is_active)
        """).bindparams(
            username="admin",
            password_hash=ADMIN_PASSWORD_HASH,
            nickname="系統管理員",
            is_admin=True,
            is_active=True,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE username = :username").bindparams(username="admin")
    )
