"""
Detection-related agent tools.

All tools are read-only wrappers over ``detection_repository``. They never
trigger YOLO inference (that remains the responsibility of
``detection_service`` / ``YoloEngine``).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import detection_repository


def _ensure_owned(task, current_user: User) -> None:
    """Raise ``PermissionError`` if ``current_user`` is not allowed to read the task."""
    if task is None:
        raise LookupError("detection task not found")
    if not current_user.is_admin and task.user_id != current_user.id:
        raise PermissionError("not allowed to access this detection task")


def _serialize_objects(task) -> list[dict[str, Any]]:
    return [
        {
            "object_index": obj.object_index,
            "class_id": obj.class_id,
            "class_name": obj.class_name,
            "confidence": round(float(obj.confidence), 4),
            "bbox": [
                round(float(obj.bbox_x1), 2),
                round(float(obj.bbox_y1), 2),
                round(float(obj.bbox_x2), 2),
                round(float(obj.bbox_y2), 2),
            ],
        }
        for obj in (task.objects or [])
    ]


def get_detection_detail_tool(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    """Return a detection task summary + object list as a serialisable dict.

    Permissions:
        - Any authenticated user can read their own detection.
        - Admins can read every detection.

    Args:
        db: Active SQLAlchemy session.
        current_user: The user making the request (used for permission check).
        detection_id: Primary key of the detection task.

    Returns:
        A dict with task metadata (``source_type``, ``status``, ``model_name``,
        timing, image size) and a list of detected objects.
    """
    try:
        task = detection_repository.get_task(db, detection_id)
        _ensure_owned(task, current_user)
        return {
            "ok": True,
            "detection_id": task.id,
            "user_id": task.user_id,
            "source_type": task.source_type,
            "source_filename": task.source_filename,
            "model_name": task.model_name,
            "status": task.status,
            "inference_ms": task.inference_ms,
            "image_width": task.image_width,
            "image_height": task.image_height,
            "frame_count": task.frame_count,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "object_count": len(task.objects or []),
            "objects": _serialize_objects(task),
        }
    except (LookupError, PermissionError) as exc:
        return {"ok": False, "error": str(exc), "detection_id": detection_id}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}", "detection_id": detection_id}


def aggregate_detection_stats(detail: dict[str, Any]) -> dict[str, Any]:
    """Compute per-class statistics from a serialized detection ``detail`` dict.

    Pure function: it takes the dict returned by :func:`get_detection_detail_tool`
    (or any dict with the same shape) and returns class counts, confidence
    ranges, and bbox size hints. It performs no I/O and runs no inference, which
    makes it directly reusable by offline evaluation harnesses that feed in
    synthetic structured detection results.

    Args:
        detail: A dict shaped like :func:`get_detection_detail_tool`'s output,
            i.e. containing ``detection_id``, ``objects`` (list of
            ``{class_name, confidence, bbox, ...}``), ``image_width``,
            ``image_height``, ``model_name`` and ``inference_ms``.

    Returns:
        A serialisable stats dict (``class_counts``, ``confidence_range``,
        ``bbox_area_stats``, ``image_size``, ``model_name``, ``inference_ms``).
    """
    detection_id = detail.get("detection_id")
    objects = detail.get("objects") or []
    if not objects:
        return {
            "ok": True,
            "detection_id": detection_id,
            "summary": "no objects detected",
            "class_counts": {},
            "confidence_range": None,
            "object_count": 0,
        }

    class_counts: dict[str, int] = {}
    confidences: list[float] = []
    bbox_areas: list[float] = []
    image_width = detail.get("image_width") or 0
    image_height = detail.get("image_height") or 0

    for obj in objects:
        class_counts[obj["class_name"]] = class_counts.get(obj["class_name"], 0) + 1
        confidences.append(float(obj["confidence"]))
        bbox = obj["bbox"]
        area = max(0.0, (bbox[2] - bbox[0])) * max(0.0, (bbox[3] - bbox[1]))
        bbox_areas.append(area)

    return {
        "ok": True,
        "detection_id": detection_id,
        "object_count": len(objects),
        "class_counts": class_counts,
        "confidence_range": {
            "min": round(min(confidences), 4),
            "max": round(max(confidences), 4),
            "avg": round(sum(confidences) / len(confidences), 4),
        },
        "bbox_area_stats": {
            "min": round(min(bbox_areas), 2) if bbox_areas else None,
            "max": round(max(bbox_areas), 2) if bbox_areas else None,
            "avg": round(sum(bbox_areas) / len(bbox_areas), 2) if bbox_areas else None,
        },
        "image_size": {"width": image_width, "height": image_height},
        "model_name": detail.get("model_name"),
        "inference_ms": detail.get("inference_ms"),
    }


def explain_detection_objects_tool(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    """Aggregate per-class statistics for a detection task.

    Returns class counts, confidence ranges, and bbox size hints — the LLM
    can use this to compose a natural-language explanation without touching
    raw model output. Does not run inference.
    """
    detail = get_detection_detail_tool(db, current_user=current_user, detection_id=detection_id)
    if not detail.get("ok"):
        return detail
    return aggregate_detection_stats(detail)


def compare_detection_results_tool(
    db: Session,
    *,
    current_user: User,
    detection_id_a: int,
    detection_id_b: int,
) -> dict[str, Any]:
    """Compare two detection tasks side-by-side (class counts + timing).

    Both tasks must be readable by ``current_user``. Returns deltas in class
    counts and basic timing.
    """
    a = explain_detection_objects_tool(db, current_user=current_user, detection_id=detection_id_a)
    b = explain_detection_objects_tool(db, current_user=current_user, detection_id=detection_id_b)
    if not a.get("ok"):
        return a
    if not b.get("ok"):
        return b

    counts_a = a.get("class_counts") or {}
    counts_b = b.get("class_counts") or {}
    all_classes = sorted(set(counts_a) | set(counts_b))
    deltas = {
        cls: {"a": counts_a.get(cls, 0), "b": counts_b.get(cls, 0)}
        for cls in all_classes
    }

    return {
        "ok": True,
        "detection_a": detection_id_a,
        "detection_b": detection_id_b,
        "class_deltas": deltas,
        "object_counts": {
            "a": a.get("object_count"),
            "b": b.get("object_count"),
        },
        "inference_ms": {
            "a": a.get("inference_ms"),
            "b": b.get("inference_ms"),
        },
        "model_name": {
            "a": a.get("model_name"),
            "b": b.get("model_name"),
        },
    }
