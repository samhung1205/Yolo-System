"""
User-related agent tools (read-only).

Important security notes:

- ``get_current_user_profile_tool`` never exposes another user's data.
- ``admin_list_users_tool`` is hard-gated on ``current_user.is_admin``; the
  permission check happens before any DB query.
- This phase intentionally does **not** expose user create / update / delete
  to the agent layer.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import user_service


def get_current_user_profile_tool(
    db: Session,
    *,
    current_user: User,
) -> dict[str, Any]:
    """Return the calling user's own profile (safe subset only)."""
    try:
        return {
            "ok": True,
            "id": current_user.id,
            "username": current_user.username,
            "nickname": current_user.nickname,
            "email": current_user.email,
            "is_admin": bool(current_user.is_admin),
            "is_active": bool(current_user.is_active),
            "register_time": current_user.register_time.isoformat()
            if current_user.register_time
            else None,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}


def admin_list_users_tool(
    db: Session,
    *,
    current_user: User,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
) -> dict[str, Any]:
    """List users for administrative purposes.

    Permissions:
        - Admin only. Returns ``ok=False`` with ``error=permission_denied``
          when called by a non-admin user (instead of raising) so the graph
          can render a friendly response.
    """
    if not current_user.is_admin:
        return {"ok": False, "error": "permission_denied"}

    try:
        page = max(1, int(page))
        limit = max(1, min(int(limit), 100))
        result = user_service.list_users(db, page=page, limit=limit, search=search)
        items = [
            {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
                "is_admin": bool(user.is_admin),
                "is_active": bool(user.is_active),
                "register_time": user.register_time.isoformat()
                if user.register_time
                else None,
            }
            for user in result.get("items", [])
        ]
        return {
            "ok": True,
            "total": result.get("total", 0),
            "page": result.get("page", page),
            "limit": result.get("limit", limit),
            "items": items,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}
