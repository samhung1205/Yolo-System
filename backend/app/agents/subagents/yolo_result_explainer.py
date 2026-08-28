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
    load_detection_image_tool,
)
from app.core.config import settings
from app.models.user import User


def run_yolo_explainer(
    db: Session,
    *,
    current_user: User,
    detection_id: int,
) -> dict[str, Any]:
    """Gather detection detail + per-class statistics for the LLM to explain.

    When ``AGENT_ENABLE_VISION`` is on, also loads the annotated result image
    so the LLM can describe what it visually observes in addition to the
    structured bbox/class data (see ``build_yolo_explainer_messages``).
    """
    detail = get_detection_detail_tool(db, current_user=current_user, detection_id=detection_id)
    if not detail.get("ok"):
        return {"ok": False, "error": detail.get("error"), "detection_id": detection_id}

    stats = explain_detection_objects_tool(
        db,
        current_user=current_user,
        detection_id=detection_id,
    )

    image: dict[str, Any] | None = None
    if settings.AGENT_ENABLE_VISION:
        image = load_detection_image_tool(db, current_user=current_user, detection_id=detection_id)

    return {
        "ok": True,
        "detection_id": detection_id,
        "detail": detail,
        "stats": stats,
        "image": image,
    }


def build_yolo_explainer_messages(
    user_message: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the message list for the LLM call.

    The structured detection payload is embedded directly in the user turn
    rather than using ``role: "tool"``. OpenAI (and other strict providers)
    require a preceding ``tool_calls`` assistant message before any ``tool``
    role message; since this payload is produced deterministically (not by a
    model-triggered function call), using the ``tool`` role would cause 400
    errors with newer OpenAI models. Embedding the data in the user message
    is equivalent semantically and works across all providers.

    When ``payload["image"]`` is a successfully-loaded image (see
    :func:`run_yolo_explainer`), the user turn becomes a multimodal content
    list (text block + ``image_url`` block) instead of a plain string, so
    vision-capable models can look at the actual annotated frame.
    """
    text_payload = {k: v for k, v in payload.items() if k != "image"}
    data_block = json.dumps(text_payload, ensure_ascii=False, indent=2)
    combined = (
        f"[Detection Analysis Data]\n{data_block}\n\n"
        f"{user_message or '請解釋這筆 YOLO 偵測結果。'}"
    )

    image = payload.get("image")
    user_content: Any = combined
    if isinstance(image, dict) and image.get("ok"):
        user_content = [
            {"type": "text", "text": combined},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image['mime_type']};base64,{image['image_base64']}"
                },
            },
        ]

    return [
        {"role": "system", "content": YOLO_RESULT_EXPLAINER_PROMPT},
        {"role": "user", "content": user_content},
    ]
