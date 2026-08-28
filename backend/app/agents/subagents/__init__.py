"""
Subagent helpers.

Each subagent is a thin function pair:

- ``run_*`` collects deterministic data via the tool layer.
- ``build_*_messages`` assembles an LLM prompt that combines the subagent's
  system prompt with that data, ready for ``llm.get_chat_model().invoke()``.

The supervisor graph orchestrates the data → LLM → final answer flow; the
subagents themselves do not call the LLM directly.
"""
from __future__ import annotations

from .admin_assistant import build_admin_assistant_messages, run_admin_assistant
from .batch_analyst import build_batch_analyst_messages, run_batch_analyst
from .detection_history_analyst import (
    build_history_analyst_messages,
    run_history_analyst,
)
from .report_agent import build_report_agent_messages, run_report_agent
from .yolo_result_explainer import (
    build_yolo_explainer_messages,
    run_yolo_explainer,
)

__all__ = [
    "build_admin_assistant_messages",
    "build_batch_analyst_messages",
    "build_history_analyst_messages",
    "build_report_agent_messages",
    "build_yolo_explainer_messages",
    "run_admin_assistant",
    "run_batch_analyst",
    "run_history_analyst",
    "run_report_agent",
    "run_yolo_explainer",
]
