"""
Startup safety checks.

Development only prints warnings; ``APP_ENV=production`` refuses to start
while any of these problems remain.
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.security import verify_password

logger = logging.getLogger(__name__)

# Values that ship in the repo (config default, .env.example) and are
# therefore public: a JWT signed with them is forgeable.
KNOWN_PLACEHOLDER_SECRETS = frozenset(
    {
        "change-me-in-production",
        "change_this_to_a_long_random_string_at_least_32_chars",
    }
)
MIN_SECRET_KEY_LENGTH = 32

# Password of the admin seeded by migration 0002 (documented in the repo).
SEEDED_ADMIN_USERNAME = "admin"
SEEDED_ADMIN_PASSWORD = "Admin@2026"


def secret_key_problems(secret_key: str) -> list[str]:
    problems = []
    if secret_key in KNOWN_PLACEHOLDER_SECRETS:
        problems.append("SECRET_KEY is a placeholder value published in the repository")
    elif len(secret_key) < MIN_SECRET_KEY_LENGTH:
        problems.append(f"SECRET_KEY is shorter than {MIN_SECRET_KEY_LENGTH} characters")
    return problems


def seeded_admin_password_unchanged(session_factory) -> bool | None:
    """True if the seeded admin still uses the default password.

    Returns None when the database cannot be reached, so a DB outage never
    blocks startup by itself (requests will fail with their own errors).
    """
    from app.models.user import User

    try:
        db = session_factory()
    except SQLAlchemyError:
        return None
    try:
        admin = db.query(User).filter(User.username == SEEDED_ADMIN_USERNAME, User.is_active == True).first()
        if admin is None:
            return False
        return verify_password(SEEDED_ADMIN_PASSWORD, admin.password_hash)
    except (SQLAlchemyError, ValueError):
        logger.warning("Could not check the seeded admin password (database unavailable?)")
        return None
    finally:
        db.close()


def run_startup_checks(settings, session_factory) -> list[str]:
    """Return the problems found; raises RuntimeError in production."""
    problems = secret_key_problems(settings.SECRET_KEY)
    if seeded_admin_password_unchanged(session_factory):
        problems.append(
            f"user '{SEEDED_ADMIN_USERNAME}' still has the default password from migration 0002"
        )
    if problems and settings.is_production:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    return problems
