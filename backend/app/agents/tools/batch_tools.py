"""
Batch-analysis tools (read-only).

Deterministic aggregate statistics across every image in a
``detection_batches`` row. Deliberately limited to per-class counting and
"zero-detection" flags for Phase 1 — spatial relationships between classes
(e.g. "ships with an airplane on deck") are a later phase.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import detection_repository

# Per-image breakdown is capped so very large batches (100+ images) don't blow
# up the LLM context; totals themselves are always computed over every image
# via SQL aggregation, so they stay accurate even when the breakdown is capped.
PER_IMAGE_BREAKDOWN_LIMIT = 50


def _get_owned_batch(db: Session, *, current_user: User, batch_id: int):
    batch = detection_repository.get_batch(db, batch_id)
    if batch is None:
        return None
    if not current_user.is_admin and batch.user_id != current_user.id:
        return None
    return batch


def summarize_batch_tool(
    db: Session,
    *,
    current_user: User,
    batch_id: int,
) -> dict[str, Any]:
    """Aggregate per-class object counts and completion stats for one batch.

    Permissions: only the batch owner (or an admin) may read it.
    """
    try:
        batch = _get_owned_batch(db, current_user=current_user, batch_id=batch_id)
        if batch is None:
            return {"ok": False, "error": "batch_not_found_or_not_owned"}

        class_counts = detection_repository.count_objects_by_class_for_batch(db, batch_id)
        total_objects = sum(count for _, count in class_counts)

        tasks = batch.tasks or []
        completed_tasks = [t for t in tasks if t.status == "completed"]
        failed_tasks = [t for t in tasks if t.status == "failed"]
        zero_detection_tasks = [t for t in completed_tasks if len(t.objects or []) == 0]

        per_image = [
            {
                "task_id": t.id,
                "filename": t.source_filename,
                "status": t.status,
                "object_count": len(t.objects or []),
                "classes": sorted({obj.class_name for obj in (t.objects or [])}),
            }
            for t in tasks[:PER_IMAGE_BREAKDOWN_LIMIT]
        ]

        return {
            "ok": True,
            "batch_id": batch.id,
            "batch_name": batch.name,
            "model_name": batch.model_name,
            "batch_status": batch.status,
            "total_files": batch.total_files,
            "completed_count": len(completed_tasks),
            "failed_count": len(failed_tasks),
            "skipped_files": batch.skipped_files or [],
            "total_objects_detected": total_objects,
            "class_counts": [{"class_name": name, "count": count} for name, count in class_counts],
            "zero_detection_image_count": len(zero_detection_tasks),
            "zero_detection_note": (
                "這些張影像未偵測到任何物件，可能是「疑似漏檢」（估計值），"
                "也可能是影像本身確實沒有目標物件；並非模型保證的漏檢結論。"
                if zero_detection_tasks
                else None
            ),
            "zero_detection_filenames": [t.source_filename for t in zero_detection_tasks[:PER_IMAGE_BREAKDOWN_LIMIT]],
            "per_image_breakdown": per_image,
            "per_image_breakdown_truncated": len(tasks) > PER_IMAGE_BREAKDOWN_LIMIT,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}


def list_batch_images_by_class_tool(
    db: Session,
    *,
    current_user: User,
    batch_id: int,
    class_name: str,
) -> dict[str, Any]:
    """List which images in the batch contain at least one object of ``class_name``."""
    try:
        batch = _get_owned_batch(db, current_user=current_user, batch_id=batch_id)
        if batch is None:
            return {"ok": False, "error": "batch_not_found_or_not_owned"}

        needle = (class_name or "").strip().lower()
        if not needle:
            return {"ok": False, "error": "class_name is required"}

        matches = []
        for task in batch.tasks or []:
            matched_objects = [obj for obj in (task.objects or []) if obj.class_name.lower() == needle]
            if matched_objects:
                matches.append(
                    {
                        "task_id": task.id,
                        "filename": task.source_filename,
                        "match_count": len(matched_objects),
                    }
                )

        return {
            "ok": True,
            "batch_id": batch.id,
            "class_name": class_name,
            "matched_image_count": len(matches),
            "matches": matches[:PER_IMAGE_BREAKDOWN_LIMIT],
            "truncated": len(matches) > PER_IMAGE_BREAKDOWN_LIMIT,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}
