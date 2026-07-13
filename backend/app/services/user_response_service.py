"""
Helpers for serializing user records with signed avatar URLs.
"""
from __future__ import annotations

from app.core.static_tokens import build_signed_static_url
from app.models.user import User
from app.schemas.user import UserRead


def to_user_read(user: User) -> UserRead:
    avatar_url = _build_avatar_url(user.avatar)
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        avatar=user.avatar,
        avatar_url=avatar_url,
        register_time=user.register_time,
        is_admin=user.is_admin,
        is_active=user.is_active,
    )


def _build_avatar_url(avatar: str | None) -> str | None:
    if not avatar:
        return None

    if "/" in avatar or "\\" in avatar:
        if avatar.startswith("/static/"):
            return build_signed_static_url(avatar)
        if avatar.startswith("static/"):
            return build_signed_static_url(avatar)
        return None

    return build_signed_static_url(f"avatars/{avatar}")
