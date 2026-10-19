"""
LangChain ``@tool`` wrappers over the read-only agent tool layer.

Used by the tool-calling engine (``app/agents/tool_agent.py``). The model only
sees the arguments listed in each signature; the DB session, the
authenticated user and the IDs selected in the UI arrive through
``ToolRuntime[AgentToolContext]`` and are never chosen by the model. Every
wrapper delegates to the existing ``app/agents/tools/*`` functions, so
ownership scoping and the admin hard checks stay exactly where they were.

All tools are read-only: nothing here creates, updates or deletes data, and
nothing runs YOLO inference.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain.tools import ToolRuntime, tool
from sqlalchemy.orm import Session

from app.agents.tools.batch_tools import list_batch_images_by_class_tool, summarize_batch_tool
from app.agents.tools.detection_tools import (
    aggregate_detection_stats,
    compare_detection_results_tool,
    get_detection_detail_tool,
)
from app.agents.tools.history_tools import (
    filter_detections_by_status_or_type_tool,
    summarize_detection_history_tool,
)
from app.agents.tools.report_tools import (
    generate_detection_report_markdown_tool,
    summarize_model_performance_tool,
)
from app.agents.tools.user_tools import admin_list_users_tool
from app.models.user import User

# Dense images can have hundreds of boxes; the per-class statistics are always
# complete, so only the per-object list is capped to keep small local models'
# context manageable.
MAX_OBJECTS_IN_TOOL_RESULT = 50


@dataclass
class AgentToolContext:
    db: Session
    current_user: User
    detection_id: Optional[int] = None
    batch_id: Optional[int] = None
    # ToolNode may run several tool calls of one model turn in parallel
    # threads; a SQLAlchemy Session must not be used concurrently.
    # Typed as Any: LangGraph builds a schema from context_schema and cannot
    # describe a lock object.
    db_lock: Any = field(default_factory=threading.Lock, repr=False)


def _missing_id(kind: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": f"{kind}_required",
        "hint": f"No {kind} was given and none is selected in the UI; ask the user which one.",
    }


def _detection_payload(ctx: AgentToolContext, detection_id: int) -> dict[str, Any]:
    detail = get_detection_detail_tool(ctx.db, current_user=ctx.current_user, detection_id=detection_id)
    if not detail.get("ok"):
        return detail
    objects = detail.get("objects") or []
    result = {key: value for key, value in detail.items() if key not in ("objects", "model_sha256", "model_class_map")}
    result["stats"] = aggregate_detection_stats(detail)
    result["objects"] = objects[:MAX_OBJECTS_IN_TOOL_RESULT]
    if len(objects) > MAX_OBJECTS_IN_TOOL_RESULT:
        result["objects_truncated"] = True
        result["objects_shown"] = MAX_OBJECTS_IN_TOOL_RESULT
    return result


@tool
def get_detection_detail(
    runtime: ToolRuntime[AgentToolContext],
    detection_id: Optional[int] = None,
) -> dict[str, Any]:
    """Read one saved YOLO detection result: model, thresholds, status, image size,
    per-class counts, confidence range and the detected objects (object_index,
    class_name, confidence, bbox). Omit detection_id to use the detection the user
    has selected."""
    ctx = runtime.context
    target = detection_id or ctx.detection_id
    if not target:
        return _missing_id("detection_id")
    with ctx.db_lock:
        return _detection_payload(ctx, int(target))


@tool
def compare_detections(
    detection_id_a: int,
    detection_id_b: int,
    runtime: ToolRuntime[AgentToolContext],
) -> dict[str, Any]:
    """Compare two saved detection results: per-class object counts and inference time."""
    ctx = runtime.context
    with ctx.db_lock:
        return compare_detection_results_tool(
            ctx.db,
            current_user=ctx.current_user,
            detection_id_a=int(detection_id_a),
            detection_id_b=int(detection_id_b),
        )


@tool
def summarize_detection_history(runtime: ToolRuntime[AgentToolContext]) -> dict[str, Any]:
    """Summarize the current user's whole detection history: totals by status and
    source type, the most common classes, and recent activity."""
    ctx = runtime.context
    with ctx.db_lock:
        return summarize_detection_history_tool(ctx.db, current_user=ctx.current_user)


@tool
def list_recent_detections(
    runtime: ToolRuntime[AgentToolContext],
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """List the current user's most recent detection tasks (newest first).
    Optional filters: status = completed / failed / processing / pending,
    source_type = image / video. limit is 1-50."""
    ctx = runtime.context
    with ctx.db_lock:
        return filter_detections_by_status_or_type_tool(
            ctx.db,
            current_user=ctx.current_user,
            status=status,
            source_type=source_type,
            limit=max(1, min(int(limit), 50)),
        )


@tool
def summarize_model_performance(runtime: ToolRuntime[AgentToolContext]) -> dict[str, Any]:
    """Summarize inference speed and outcomes per YOLO model across the user's history."""
    ctx = runtime.context
    with ctx.db_lock:
        return summarize_model_performance_tool(ctx.db, current_user=ctx.current_user)


@tool
def generate_detection_report(
    runtime: ToolRuntime[AgentToolContext],
    detection_id: Optional[int] = None,
) -> dict[str, Any]:
    """Build the standard markdown report for one saved detection result.
    Omit detection_id to use the detection the user has selected."""
    ctx = runtime.context
    target = detection_id or ctx.detection_id
    if not target:
        return _missing_id("detection_id")
    with ctx.db_lock:
        return generate_detection_report_markdown_tool(
            ctx.db, current_user=ctx.current_user, detection_id=int(target)
        )


@tool
def summarize_batch(
    runtime: ToolRuntime[AgentToolContext],
    batch_id: Optional[int] = None,
) -> dict[str, Any]:
    """Summarize a batch of images: total images, per-class object totals across the
    batch, failed images, and images with zero detections (possible misses — an
    estimate, not a confirmed miss). Omit batch_id to use the selected batch."""
    ctx = runtime.context
    target = batch_id or ctx.batch_id
    if not target:
        return _missing_id("batch_id")
    with ctx.db_lock:
        return summarize_batch_tool(ctx.db, current_user=ctx.current_user, batch_id=int(target))


@tool
def list_batch_images_by_class(
    class_name: str,
    runtime: ToolRuntime[AgentToolContext],
    batch_id: Optional[int] = None,
) -> dict[str, Any]:
    """List which images in a batch contain at least one object of class_name
    (use the exact class name, e.g. "ship"). Omit batch_id to use the selected batch."""
    ctx = runtime.context
    target = batch_id or ctx.batch_id
    if not target:
        return _missing_id("batch_id")
    with ctx.db_lock:
        return list_batch_images_by_class_tool(
            ctx.db, current_user=ctx.current_user, batch_id=int(target), class_name=class_name
        )


@tool
def admin_list_users(
    runtime: ToolRuntime[AgentToolContext],
    search: Optional[str] = None,
    page: int = 1,
) -> dict[str, Any]:
    """Admin only: list user accounts (username, nickname, role, active flag),
    20 per page, optionally filtered by a search string."""
    ctx = runtime.context
    if not ctx.current_user.is_admin:
        return {"ok": False, "error": "permission_denied"}
    with ctx.db_lock:
        return admin_list_users_tool(ctx.db, current_user=ctx.current_user, page=page, limit=20, search=search)


@tool
def admin_detection_overview(runtime: ToolRuntime[AgentToolContext]) -> dict[str, Any]:
    """Admin only: summarize detection activity across all users."""
    ctx = runtime.context
    if not ctx.current_user.is_admin:
        return {"ok": False, "error": "permission_denied"}
    with ctx.db_lock:
        return summarize_detection_history_tool(ctx.db, current_user=ctx.current_user, user_id=None)


DETECTION_TOOLS = [get_detection_detail, compare_detections]
HISTORY_TOOLS = [summarize_detection_history, list_recent_detections, summarize_model_performance]
REPORT_TOOLS = [generate_detection_report]
BATCH_TOOLS = [summarize_batch, list_batch_images_by_class]
ADMIN_TOOLS = [admin_list_users, admin_detection_overview]

USER_TOOLS = DETECTION_TOOLS + HISTORY_TOOLS + REPORT_TOOLS + BATCH_TOOLS
