"""
Detection history analyst subagent.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.prompts import DETECTION_HISTORY_ANALYST_PROMPT
from app.agents.tools.history_tools import (
    list_recent_detections_tool,
    summarize_detection_history_tool,
)
from app.models.user import User


def run_history_analyst(
    db: Session,
    *,
    current_user: User,
    user_id: Optional[int] = None,
    recent_limit: int = 5,
) -> dict[str, Any]:
    summary = summarize_detection_history_tool(
        db,
        current_user=current_user,
        user_id=user_id,
    )
    recent = list_recent_detections_tool(
        db,
        current_user=current_user,
        user_id=user_id,
        limit=recent_limit,
    )
    return {
        "ok": True,
        "summary": summary,
        "recent": recent,
    }


def build_history_analyst_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Embed the structured payload in the user turn instead of ``role: "tool"``.

    OpenAI (and other strict providers) reject ``tool`` role messages that are
    not preceded by an assistant ``tool_calls`` message; since this payload is
    produced deterministically, embedding it in the user message is equivalent
    and works across all providers. (Same pattern as yolo_result_explainer.)
    """
    data_block = json.dumps(payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Detection History Data]\n{data_block}\n\n"
        f"{user_message or '請摘要我最近的 YOLO 偵測記錄。'}"
    )
    return [
        {"role": "system", "content": DETECTION_HISTORY_ANALYST_PROMPT},
        {"role": "user", "content": combined},
    ]
