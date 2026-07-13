"""
Authorization helpers for protected static assets.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.static_tokens import normalize_static_relative_path
from app.models.detection_task import DetectionTask
from app.models.user import User

STATIC_ROOT = Path("static")


def resolve_static_file(relative_path: str) -> Path:
    """Resolve a static relative path to an on-disk file."""
    normalized = normalize_static_relative_path(relative_path)
    static_root = STATIC_ROOT.resolve()
    full_path = (static_root / normalized).resolve()

    try:
        full_path.relative_to(static_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid static path") from exc

    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Static asset not found")

    return full_path


def user_can_access_static_path(db: Session, *, current_user: User, relative_path: str) -> bool:
    """Check whether an authenticated user may read a static asset."""
    normalized = normalize_static_relative_path(relative_path)

    if normalized.startswith("avatars/"):
        # Any authenticated user may view avatars (admin user list, profile pages).
        return True

    if normalized.startswith("detections/") or normalized.startswith("results/"):
        task = _get_task_by_media_path(db, normalized)
        if task is None:
            return False
        return current_user.is_admin or task.user_id == current_user.id

    return False


def _get_task_by_media_path(db: Session, relative_path: str) -> DetectionTask | None:
    return (
        db.query(DetectionTask)
        .filter(
            or_(
                DetectionTask.source_image_path == relative_path,
                DetectionTask.result_image_path == relative_path,
                DetectionTask.source_video_path == relative_path,
                DetectionTask.result_video_path == relative_path,
                DetectionTask.preview_image_path == relative_path,
            )
        )
        .first()
    )
