"""
Agent tool collection.

Tools are plain Python callables wrapped around the existing service /
repository layer. They are intentionally read-only:

- No tool writes, updates or deletes data.
- No tool triggers YOLO inference directly; only existing detection records
  are read.
- ``user_id`` / ``current_user`` scoping is enforced inside every tool.
- Admin-only tools raise :class:`PermissionError` early so the supervisor
  graph can render a friendly message.

Each helper returns a JSON-serialisable dict so callers (LangGraph nodes,
subagents, tests) can serialise the value as the tool message body.
"""
from __future__ import annotations

from .detection_tools import (
    aggregate_detection_stats,
    compare_detection_results_tool,
    explain_detection_objects_tool,
    get_detection_detail_tool,
)
from .history_tools import (
    filter_detections_by_status_or_type_tool,
    list_recent_detections_tool,
    summarize_detection_history_tool,
)
from .report_tools import (
    generate_detection_report_markdown_tool,
    summarize_model_performance_tool,
)
from .user_tools import (
    admin_list_users_tool,
    get_current_user_profile_tool,
)

__all__ = [
    "aggregate_detection_stats",
    "compare_detection_results_tool",
    "explain_detection_objects_tool",
    "get_detection_detail_tool",
    "filter_detections_by_status_or_type_tool",
    "list_recent_detections_tool",
    "summarize_detection_history_tool",
    "generate_detection_report_markdown_tool",
    "summarize_model_performance_tool",
    "admin_list_users_tool",
    "get_current_user_profile_tool",
]
