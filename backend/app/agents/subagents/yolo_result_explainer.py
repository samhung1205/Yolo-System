"""
YOLO result explainer subagent.

Collects deterministic per-detection statistics via the tool layer, then
prepares the prompt messages that the supervisor graph will hand to the LLM.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.prompts import YOLO_RESULT_EXPLAINER_PROMPT
from app.agents.tools.detection_tools import (
    explain_detection_objects_tool,
    get_detection_detail_tool,
)
from app.models.user import User


def run_yolo_explainer(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    """Gather detection detail + per-class statistics for the LLM to explain."""
    detail = get_detection_detail_tool(db, current_user=current_user, detection_id=detection_id)
    if not detail.get("ok"):
        return {"ok": False, "error": detail.get("error"), "detection_id": detection_id}

    stats = explain_detection_objects_tool(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )
    return {
        "ok": True,
        "detection_id": detection_id,
        "detail": detail,
        "stats": stats,
    }


def build_yolo_explainer_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Build the message list for the LLM call.

    The structured detection payload is embedded directly in the user turn
    rather than using ``role: "tool"``. OpenAI (and other strict providers)
    require a preceding ``tool_calls`` assistant message before any ``tool``
    role message; since this payload is produced deterministically (not by a
    model-triggered function call), using the ``tool`` role would cause 400
    errors with newer OpenAI models. Embedding the data in the user message
    is equivalent semantically and works across all providers.
    """
    data_block = json.dumps(payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Detection Analysis Data]\n{data_block}\n\n"
        f"{user_message or '請解釋這筆 YOLO 偵測結果。'}"
    )
    return [
        {"role": "system", "content": YOLO_RESULT_EXPLAINER_PROMPT},
        {"role": "user", "content": combined},
    ]
