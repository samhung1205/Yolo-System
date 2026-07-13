"""
Report-generation agent tools (read-only).

These tools build deterministic markdown reports / summaries. The supervisor
graph typically pairs the output of these helpers with an LLM-driven narrative
section, but the underlying numbers always come from this module — never from
the LLM.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import detection_repository

from .detection_tools import explain_detection_objects_tool, get_detection_detail_tool


def generate_detection_report_markdown_tool(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    """Render a markdown report for one detection task.

    Permissions:
        - Same as :func:`get_detection_detail_tool` (owner or admin).
    """
    detail = get_detection_detail_tool(db, current_user=current_user, detection_id=detection_id)
    if not detail.get("ok"):
        return detail
    stats = explain_detection_objects_tool(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )

    lines: list[str] = []
    lines.append("# YOLO Detection Report")
    lines.append("")
    lines.append("## 1. Task Summary")
    lines.append(f"- detection_id: {detail['detection_id']}")
    lines.append(f"- user_id: {detail['user_id']}")
    lines.append(f"- status: {detail['status']}")
    lines.append(f"- created_at: {detail.get('created_at')}")
    lines.append("")

    lines.append("## 2. Input Source")
    lines.append(f"- source_type: {detail['source_type']}")
    lines.append(f"- source_filename: {detail['source_filename']}")
    if detail.get("frame_count") is not None:
        lines.append(f"- frame_count: {detail['frame_count']}")
    if detail.get("image_width") and detail.get("image_height"):
        lines.append(
            f"- image_size: {detail['image_width']} x {detail['image_height']}"
        )
    lines.append("")

    lines.append("## 3. Model and Inference")
    lines.append(f"- model_name: {detail['model_name']}")
    lines.append(f"- inference_ms: {detail.get('inference_ms')}")
    if detail.get("error_message"):
        lines.append(f"- error_message: {detail['error_message']}")
    lines.append("")

    lines.append("## 4. Detected Objects")
    objects = detail.get("objects") or []
    if not objects:
        lines.append("_No objects detected._")
    else:
        lines.append("| # | class | confidence | bbox (x1, y1, x2, y2) |")
        lines.append("|---|-------|------------|------------------------|")
        for obj in objects:
            bbox = obj["bbox"]
            lines.append(
                f"| {obj['object_index']} | {obj['class_name']} | {obj['confidence']:.4f} | "
                f"({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}) |"
            )
    lines.append("")

    lines.append("## 5. Interpretation")
    class_counts = stats.get("class_counts") or {}
    if class_counts:
        rendered = ", ".join(f"{cls} x{count}" for cls, count in class_counts.items())
        lines.append(f"- Detected classes: {rendered}")
    confidence_range = stats.get("confidence_range")
    if confidence_range:
        lines.append(
            f"- Confidence: min={confidence_range['min']}, "
            f"avg={confidence_range['avg']}, max={confidence_range['max']}"
        )
    lines.append("")

    lines.append("## 6. Limitations")
    lines.append("- Results are YOLO model predictions, not human annotations.")
    lines.append(
        "- Low-confidence detections may include false positives; high-confidence "
        "detections may still be wrong on out-of-distribution inputs."
    )
    lines.append(
        "- Bounding boxes describe model output; they do not segment the object."
    )
    lines.append("")

    lines.append("## 7. Suggested Next Steps")
    lines.append("- Review detection result image / video on the detection history page.")
    lines.append("- If a class is consistently missed, consider fine-tuning the model.")
    lines.append("- For ambiguous detections, capture additional samples for evaluation.")
    lines.append("")

    return {
        "ok": True,
        "detection_id": detection_id,
        "markdown": "\n".join(lines),
        "object_count": len(objects),
    }


def summarize_model_performance_tool(
    db: Session,
    *,
    current_user: User,
) -> dict[str, Any]:
    """Aggregate basic performance statistics across the user's detection history.

    Non-admin users see only their own tasks; admins see global aggregates.
    """
    try:
        from app.agents.tools.history_tools import HISTORY_SCAN_LIMIT

        scope = None if current_user.is_admin else current_user.id
        tasks = detection_repository.list_tasks(db, user_id=scope, limit=HISTORY_SCAN_LIMIT)
        if not tasks:
            return {
                "ok": True,
                "scope_user_id": scope,
                "total_tasks": 0,
                "models": {},
            }

        per_model: dict[str, dict[str, Any]] = {}
        for task in tasks:
            model = task.model_name or "unknown"
            slot = per_model.setdefault(
                model,
                {
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "processing": 0,
                    "inference_ms": [],
                    "class_counter": Counter(),
                },
            )
            slot["total"] += 1
            status_key = (task.status or "").lower()
            if status_key in ("completed", "failed", "processing"):
                slot[status_key] += 1
            if task.inference_ms is not None:
                slot["inference_ms"].append(float(task.inference_ms))
            for obj in task.objects or []:
                slot["class_counter"][obj.class_name] += 1

        result: dict[str, dict[str, Any]] = {}
        for model, info in per_model.items():
            inf = info["inference_ms"]
            result[model] = {
                "total": info["total"],
                "completed": info["completed"],
                "failed": info["failed"],
                "processing": info["processing"],
                "inference_ms_avg": round(sum(inf) / len(inf), 2) if inf else None,
                "top_classes": info["class_counter"].most_common(5),
            }

        return {
            "ok": True,
            "scope_user_id": scope,
            "total_tasks": len(tasks),
            "models": result,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"unexpected error: {exc}"}
