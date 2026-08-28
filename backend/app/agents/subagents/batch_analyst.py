"""
Batch analyst subagent — aggregate Q&A across a multi-image detection batch.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.prompts import BATCH_ANALYST_PROMPT
from app.agents.tools.batch_tools import summarize_batch_tool
from app.models.user import User


def run_batch_analyst(
    db: Session,
    *,
    current_user: User,
    batch_id: int,
) -> dict[str, Any]:
    summary = summarize_batch_tool(db, current_user=current_user, batch_id=batch_id)
    if not summary.get("ok"):
        return {"ok": False, "error": summary.get("error", "batch summary failed")}
    return {"ok": True, "summary": summary}


def build_batch_analyst_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Embed the structured payload in the user turn (same pattern as the
    other subagents — avoids ``role: "tool"`` messages that OpenAI rejects
    without a preceding ``tool_calls`` assistant turn)."""
    data_block = json.dumps(payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Detection Batch Data]\n{data_block}\n\n"
        f"{user_message or '請統計這批影像的偵測結果。'}"
    )
    return [
        {"role": "system", "content": BATCH_ANALYST_PROMPT},
        {"role": "user", "content": combined},
    ]
