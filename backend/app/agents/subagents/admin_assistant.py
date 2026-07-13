"""
Admin assistant subagent.

The admin_help intent is gated at the graph layer (a non-admin caller never
reaches this subagent). As a defence-in-depth measure each tool used here
also enforces ``current_user.is_admin``.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.prompts import ADMIN_ASSISTANT_PROMPT
from app.agents.tools.history_tools import summarize_detection_history_tool
from app.agents.tools.user_tools import admin_list_users_tool
from app.models.user import User


def run_admin_assistant(
    db: Session,
    *,
    current_user: User,
    list_limit: int = 10,
) -> dict[str, Any]:
    users = admin_list_users_tool(
        db,
        current_user=current_user,
        page=1,
        limit=list_limit,
    )
    detections = summarize_detection_history_tool(
        db,
        current_user=current_user,
        user_id=None,
    )
    return {
        "ok": users.get("ok", False) and detections.get("ok", False),
        "users": users,
        "detections": detections,
    }


def build_admin_assistant_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Embed the structured payload in the user turn instead of ``role: "tool"``
    (strict providers such as OpenAI reject orphan tool messages — see
    yolo_result_explainer for the full rationale)."""
    data_block = json.dumps(payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Admin Overview Data]\n{data_block}\n\n"
        f"{user_message or '請彙整目前系統的使用者數量、最近的偵測情況，以及任何值得關注的指標。'}"
    )
    return [
        {"role": "system", "content": ADMIN_ASSISTANT_PROMPT},
        {"role": "user", "content": combined},
    ]
