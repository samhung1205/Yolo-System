"""
Detection-history analytics tools (read-only).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import detection_repository

# Upper bound of tasks scanned by the aggregate tools. The repository default
# (100) silently skewed statistics for active users; 1000 keeps memory bounded
# while covering realistic history sizes. Payloads report ``truncated`` so the
# LLM can mention when statistics are partial.
HISTORY_SCAN_LIMIT = 1000


def _scope_user_id(current_user: User, requested_user_id: Optional[int]) -> Optional[int]:
    """Resolve which user's history the tool should scan.

    - Non-admin users always see their own data; ``requested_user_id`` is
      ignored.
    - Admins may scope to a specific user, or pass ``None`` for "all users".
    """
    if not current_user.is_admin:
        return current_user.id
    return requested_user_id


def _summarize_task(task) -> dict[str, Any]:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "source_type": task.source_type,
        "source_filename": task.source_filename,
        "model_name": task.model_name,
        "status": task.status,
        "inference_ms": task.inference_ms,
        "object_count": len(task.objects or []),
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def list_recent_detections_tool(
    db: Session,
    *,
    current_user: User,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the most recent detection tasks visible to ``current_user``.

    Permissions:
        - Non-admin: always scoped to ``current_user.id``.
        - Admin: ``user_id=None`` returns global recent tasks, otherwise
          scoped to the specified user.
    """
    try:
        limit = max(1, min(int(limit), 50))
        scope = _scope_user_id(current_user, user_id)
        tasks = detection_repository.list_tasks(db, user_id=scope, limit=limit)
        return {
            "ok": True,
            "scope_user_id": scope,
            "count": len(tasks),
            "items": [_summarize_task(task) for task in tasks],
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}


def summarize_detection_history_tool(
    db: Session,
    *,
    current_user: User,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    """Aggregate counts and basic statistics across the scoped detection history."""
    try:
        scope = _scope_user_id(current_user, user_id)
        total_tasks = detection_repository.count_tasks(db, user_id=scope)
        tasks = detection_repository.list_tasks(db, user_id=scope, limit=HISTORY_SCAN_LIMIT)

        status_counter: Counter[str] = Counter()
        source_type_counter: Counter[str] = Counter()
        class_counter: Counter[str] = Counter()
        inference_times: list[float] = []

        for task in tasks:
            status_counter[task.status or "unknown"] += 1
            source_type_counter[task.source_type or "unknown"] += 1
            if task.inference_ms is not None:
                inference_times.append(float(task.inference_ms))
            for obj in task.objects or []:
                class_counter[obj.class_name] += 1

        return {
            "ok": True,
            "scope_user_id": scope,
            "total_tasks": total_tasks,
            "analyzed_tasks": len(tasks),
            "truncated": total_tasks > len(tasks),
            "status_counts": dict(status_counter),
            "source_type_counts": dict(source_type_counter),
            "top_classes": class_counter.most_common(10),
            "inference_ms_stats": {
                "samples": len(inference_times),
                "avg": round(sum(inference_times) / len(inference_times), 2)
                if inference_times
                else None,
                "min": round(min(inference_times), 2) if inference_times else None,
                "max": round(max(inference_times), 2) if inference_times else None,
            },
            "most_recent": _summarize_task(tasks[0]) if tasks else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}


def filter_detections_by_status_or_type_tool(
    db: Session,
    *,
    current_user: User,
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Filter detection history by status (``processing`` / ``completed`` / ``failed``)
    and/or ``source_type`` (``image`` / ``video``).
    """
    try:
        limit = max(1, min(int(limit), 100))
        scope = _scope_user_id(current_user, user_id)

        normalized_status = (status or "").strip().lower() or None
        normalized_type = (source_type or "").strip().lower() or None

        # Filter in SQL so results are not capped by the repository default
        # limit before the filter is applied.
        filtered = detection_repository.list_tasks(
            db,
            user_id=scope,
            status=normalized_status,
            source_type=normalized_type,
            limit=limit,
        )
        return {
            "ok": True,
            "scope_user_id": scope,
            "filters": {"status": normalized_status, "source_type": normalized_type},
            "count": len(filtered),
            "items": [_summarize_task(task) for task in filtered],
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}
