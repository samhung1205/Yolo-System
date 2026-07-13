"""
Agent service layer.

Provides ``create_agent_reply()`` which runs the LangGraph supervisor and
persists the conversation turn in the existing ``chat_logs`` table using
``provider="langgraph-agent"`` so it does not collide with ``/api/chat``
records (provider="openai"/"deepseek"/"mock").
"""
from __future__ import annotations

import json
import logging
from typing import Any, Generator, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agents.graph import describe_runtime, run_graph, stream_graph
from app.agents.llm import langchain_available, langgraph_available
from app.core.config import settings
from app.models.user import User
from app.repositories import chat_repository
from app.schemas.agent import AgentChatResponse

logger = logging.getLogger(__name__)

AGENT_PROVIDER_TAG = "langgraph-agent"


def _build_history_messages(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
) -> list[dict[str, str]]:
    """Reuse chat_logs to provide multi-turn context to the agent."""
    limit = max(1, int(settings.AGENT_MAX_HISTORY_TURNS or 10))
    logs = chat_repository.get_recent_conversation_logs(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
    )
    messages: list[dict[str, str]] = []
    for log in logs:
        messages.append({"role": "user", "content": log.question})
        messages.append({"role": "assistant", "content": log.answer})
    return messages


def _format_user_facing_error(exc: Exception) -> str:
    """Avoid leaking internal traceback details to the API consumer."""
    logger.exception("Agent service failure")
    return "Agent 暫時無法回覆，請稍後再試。"


def create_agent_reply(
    db: Session,
    *,
    current_user: User,
    message: str,
    conversation_id: Optional[str] = None,
    mode: str = "auto",
    detection_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
) -> AgentChatResponse:
    """Execute the agent workflow and persist the turn.

    Args:
        db: Active SQLAlchemy session.
        current_user: Authenticated caller; used for permissions / scoping.
        message: User's latest message.
        conversation_id: Optional existing conversation id; a new one is
            generated when missing or blank.
        mode: One of ``auto`` / ``general_chat`` / ``explain_detection`` /
            ``history_analysis`` / ``report`` / ``admin_help``.
        detection_id: Required for ``explain_detection`` / ``report``.

    Returns:
        :class:`AgentChatResponse`.
    """
    normalized_conversation_id = (conversation_id or "").strip() or uuid4().hex
    safe_mode = (mode or "auto").strip().lower() or "auto"

    if not langchain_available() and not langgraph_available():
        runtime = describe_runtime()
        return AgentChatResponse(
            conversation_id=normalized_conversation_id,
            answer=runtime.get("agent_unavailable_message", "Agent unavailable"),
            mode=safe_mode,
            tool_calls=[],
            references=[],
            success=False,
            errors=["agent_runtime_unavailable"],
        )

    history_messages = _build_history_messages(
        db,
        user_id=current_user.id,
        conversation_id=normalized_conversation_id,
    )

    try:
        result = run_graph(
            db=db,
            current_user=current_user,
            message=message,
            history_messages=history_messages,
            conversation_id=normalized_conversation_id,
            mode=safe_mode,
            detection_id=detection_id,
            provider_name=provider_name,
            model_name_override=model_name_override,
        )
    except Exception as exc:  # pragma: no cover - defensive
        answer = _format_user_facing_error(exc)
        return AgentChatResponse(
            conversation_id=normalized_conversation_id,
            answer=answer,
            mode=safe_mode,
            tool_calls=[],
            references=[],
            success=False,
            errors=["agent_service_failure"],
        )

    answer = result.get("final_answer") or "(no answer)"
    tool_results = result.get("tool_results") or []
    references = result.get("references") or []
    errors = result.get("errors") or []

    # Persist the turn alongside provider-based chat history so users keep a
    # unified record. provider="langgraph-agent" prevents collision with
    # /api/chat's provider field.
    if not errors:
        try:
            turn_index = chat_repository.get_next_turn_index(
                db,
                user_id=current_user.id,
                conversation_id=normalized_conversation_id,
            )
            effective_model = model_name_override or settings.agent_effective_model
            chat_repository.create_log(
                db,
                user_id=current_user.id,
                conversation_id=normalized_conversation_id,
                turn_index=turn_index,
                provider=AGENT_PROVIDER_TAG,
                model_name=effective_model,
                question=message,
                answer=answer,
            )
        except Exception:  # pragma: no cover - logging is best-effort
            logger.exception("Failed to persist agent chat log")

    return AgentChatResponse(
        conversation_id=normalized_conversation_id,
        answer=answer,
        mode=safe_mode,
        tool_calls=tool_results,
        references=references,
        success=not errors,
        errors=errors,
    )


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_agent_reply(
    db: Session,
    *,
    current_user: User,
    message: str,
    conversation_id: Optional[str] = None,
    mode: str = "auto",
    detection_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
) -> Generator[str, None, None]:
    """SSE generator for ``POST /api/agent/chat/stream``.

    Emits events in the same format as ``/api/chat/stream``:

    * ``{"type": "start", "conversation_id": ..., "mode": ..., "tool_calls": [...], "references": [...]}``
    * ``{"type": "chunk", "delta": "..."}``  — one or more times
    * ``{"type": "done",  "conversation_id": ..., "answer": "...", "mode": ..., "tool_calls": [...], "references": [...]}``
    * ``{"type": "error", "message": "..."}``  — only on failure
    """
    normalized_conversation_id = (conversation_id or "").strip() or uuid4().hex
    safe_mode = (mode or "auto").strip().lower() or "auto"

    def event_stream() -> Generator[str, None, None]:
        if not langchain_available() and not langgraph_available():
            runtime = describe_runtime()
            mock_answer = runtime.get("agent_unavailable_message", "Agent unavailable")
            yield _sse_event({
                "type": "start",
                "conversation_id": normalized_conversation_id,
                "mode": safe_mode,
                "tool_calls": [],
                "references": [],
            })
            yield _sse_event({"type": "chunk", "delta": mock_answer})
            yield _sse_event({
                "type": "done",
                "conversation_id": normalized_conversation_id,
                "answer": mock_answer,
                "mode": safe_mode,
                "tool_calls": [],
                "references": [],
            })
            return

        history_messages = _build_history_messages(
            db,
            user_id=current_user.id,
            conversation_id=normalized_conversation_id,
        )

        full_answer_parts: list[str] = []
        tool_results: list[dict] = []
        references: list[dict] = []

        try:
            for phase, data in stream_graph(
                db=db,
                current_user=current_user,
                message=message,
                history_messages=history_messages,
                conversation_id=normalized_conversation_id,
                mode=safe_mode,
                detection_id=detection_id,
                provider_name=provider_name,
                model_name_override=model_name_override,
            ):
                if phase == "ready":
                    tool_results = data.get("tool_results") or []
                    references = data.get("references") or []
                    yield _sse_event({
                        "type": "start",
                        "conversation_id": normalized_conversation_id,
                        "mode": safe_mode,
                        "tool_calls": tool_results,
                        "references": references,
                    })

                elif phase == "answer_chunk":
                    delta = data or ""
                    full_answer_parts.append(delta)
                    yield _sse_event({"type": "chunk", "delta": delta})

                elif phase == "done":
                    final_answer = (data.get("final_answer") or "".join(full_answer_parts)).strip()
                    tool_results = data.get("tool_results") or tool_results
                    references = data.get("references") or references

                    try:
                        turn_index = chat_repository.get_next_turn_index(
                            db,
                            user_id=current_user.id,
                            conversation_id=normalized_conversation_id,
                        )
                        effective_model = model_name_override or settings.agent_effective_model
                        chat_repository.create_log(
                            db,
                            user_id=current_user.id,
                            conversation_id=normalized_conversation_id,
                            turn_index=turn_index,
                            provider=AGENT_PROVIDER_TAG,
                            model_name=effective_model,
                            question=message,
                            answer=final_answer,
                        )
                    except Exception:
                        logger.exception("Failed to persist streamed agent chat log")

                    yield _sse_event({
                        "type": "done",
                        "conversation_id": normalized_conversation_id,
                        "answer": final_answer,
                        "mode": safe_mode,
                        "tool_calls": tool_results,
                        "references": references,
                    })

                elif phase == "error":
                    yield _sse_event({"type": "error", "message": str(data)})

        except Exception as exc:
            logger.exception("stream_agent_reply pipeline failure")
            yield _sse_event({"type": "error", "message": f"Agent streaming failed: {exc}"})

    return event_stream()
