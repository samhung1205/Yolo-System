"""
FastAPI dependencies: database session and current user extraction.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def resolve_user_from_token(db: Session, token: str) -> User | None:
    """Return the active user a JWT belongs to, or None if it is not valid.

    Besides signature / expiry, the token's ``ver`` claim must match the
    user's current ``token_version`` (tokens from before a password change,
    deactivation or role change are rejected; tokens without ``ver`` predate
    migration 0012 and count as version 0).
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    try:
        user_id = int(payload.get("sub"))
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError):
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None or token_version != (user.token_version or 0):
        return None
    return user


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Decode JWT and return the authenticated user."""
    user = resolve_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin role. Raises 403 if user is not admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
