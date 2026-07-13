"""
Report agent subagent — wraps the deterministic markdown report.

The report tool already produces a structured markdown document. The LLM is
used here to (optionally) add a short narrative interpretation paragraph. The
deterministic markdown is always preserved verbatim in the output so the user
always receives the auditable report.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agents.prompts import REPORT_AGENT_PROMPT
from app.agents.tools.report_tools import generate_detection_report_markdown_tool
from app.models.user import User


def run_report_agent(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    return generate_detection_report_markdown_tool(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )


def build_report_agent_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Embed the structured payload in the user turn instead of ``role: "tool"``
    (strict providers such as OpenAI reject orphan tool messages — see
    yolo_result_explainer for the full rationale)."""
    data_block = json.dumps(payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Detection Report Data]\n{data_block}\n\n"
        f"{user_message or '請依照上面的偵測資料產出一份 markdown 報告，並補一段簡短的解讀。'}"
    )
    return [
        {"role": "system", "content": REPORT_AGENT_PROMPT},
        {"role": "user", "content": combined},
    ]
