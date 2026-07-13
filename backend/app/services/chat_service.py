"""
Chat business logic using provider-based cloud integrations.
"""
import json
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.chat_providers.base import (
    BaseChatProvider,
    ChatProviderConfigurationError,
    ChatProviderRequestError,
)
from app.integrations.chat_providers.deepseek_provider import DeepSeekChatProvider
from app.integrations.chat_providers.mock_provider import MockChatProvider
from app.integrations.chat_providers.ollama_provider import OllamaChatProvider
from app.integrations.chat_providers.openai_provider import OpenAIChatProvider
from app.models.chat_log import ChatLog
from app.models.user import User
from app.repositories import chat_repository
from app.schemas.chat import ChatConversationRead, ChatConversationSummaryRead, ChatRead


def create_chat_reply(
    db: Session,
    *,
    current_user: User,
    question: str,
    conversation_id: str | None = None,
    provider_name: str | None = None,
    model_name_override: str | None = None,
) -> ChatRead:
    normalized_conversation_id = (conversation_id or "").strip() or uuid4().hex
    try:
        provider = _get_provider(provider_name=provider_name, model_name_override=model_name_override)
        history = _build_history(
            db,
            user_id=current_user.id,
            conversation_id=normalized_conversation_id,
        )
        completion = provider.chat(question, history=history)
    except ChatProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ChatProviderRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    turn_index = chat_repository.get_next_turn_index(
        db,
        user_id=current_user.id,
        conversation_id=normalized_conversation_id,
    )
    chat_log = chat_repository.create_log(
        db,
        user_id=current_user.id,
        conversation_id=normalized_conversation_id,
        turn_index=turn_index,
        provider=completion.provider,
        model_name=completion.model_name,
        question=question,
        answer=completion.answer,
    )
    return ChatRead.model_validate(chat_log)


def stream_chat_reply(
    *,
    user_id: int,
    question: str,
    conversation_id: str | None = None,
    provider_name: str | None = None,
    model_name_override: str | None = None,
):
    normalized_conversation_id = (conversation_id or "").strip() or uuid4().hex

    def event_stream():
        db = SessionLocal()
        full_answer_parts: list[str] = []
        completion_provider = None
        completion_model_name = None
        turn_index = 1

        try:
            provider = _get_provider(provider_name=provider_name, model_name_override=model_name_override)
            completion_provider = provider.provider_name
            completion_model_name = getattr(provider, "model_name", "")
            history = _build_history(
                db,
                user_id=user_id,
                conversation_id=normalized_conversation_id,
            )
            turn_index = chat_repository.get_next_turn_index(
                db,
                user_id=user_id,
                conversation_id=normalized_conversation_id,
            )

            yield _sse_event(
                {
                    "type": "start",
                    "conversation_id": normalized_conversation_id,
                    "turn_index": turn_index,
                    "provider": completion_provider,
                    "model_name": completion_model_name,
                }
            )

            for chunk in provider.stream_chat(question, history=history):
                if not chunk:
                    continue
                full_answer_parts.append(chunk)
                yield _sse_event({"type": "chunk", "delta": chunk})

            answer = "".join(full_answer_parts).strip()
            if not answer:
                raise ChatProviderRequestError("Provider did not return any assistant content")

            chat_log = chat_repository.create_log(
                db,
                user_id=user_id,
                conversation_id=normalized_conversation_id,
                turn_index=turn_index,
                provider=completion_provider or "",
                model_name=completion_model_name or "",
                question=question,
                answer=answer,
            )

            yield _sse_event(
                {
                    "type": "done",
                    "id": chat_log.id,
                    "user_id": chat_log.user_id,
                    "conversation_id": chat_log.conversation_id,
                    "turn_index": chat_log.turn_index,
                    "provider": chat_log.provider,
                    "model_name": chat_log.model_name,
                    "question": chat_log.question,
                    "answer": chat_log.answer,
                    "created_at": chat_log.created_at.isoformat(),
                }
            )
        except ChatProviderConfigurationError as exc:
            yield _sse_event({"type": "error", "message": str(exc)})
        except ChatProviderRequestError as exc:
            yield _sse_event({"type": "error", "message": str(exc)})
        except Exception as exc:
            yield _sse_event({"type": "error", "message": f"Streaming chat failed: {exc}"})
        finally:
            db.close()

    return event_stream()


def list_chat_conversations(
    db: Session,
    *,
    current_user: User,
    limit: int = 50,
) -> list[ChatConversationSummaryRead]:
    rows = chat_repository.list_logs(db, user_id=current_user.id, limit=limit * 20)
    conversation_ids: list[str] = []
    for row in rows:
        if row.conversation_id not in conversation_ids:
            conversation_ids.append(row.conversation_id)
        if len(conversation_ids) >= limit:
            break

    summaries: list[ChatConversationSummaryRead] = []
    for conversation_id in conversation_ids:
        messages = chat_repository.get_conversation_logs(
            db,
            user_id=current_user.id,
            conversation_id=conversation_id,
        )
        if not messages:
            continue
        first = messages[0]
        last = messages[-1]
        summaries.append(
            ChatConversationSummaryRead(
                conversation_id=conversation_id,
                title=_build_conversation_title(first.question),
                provider=last.provider,
                model_name=last.model_name,
                turn_count=len(messages),
                last_question=last.question,
                last_answer_preview=_truncate_text(last.answer, 120),
                created_at=first.created_at,
                updated_at=last.created_at,
            )
        )

    summaries.sort(key=lambda item: item.updated_at, reverse=True)
    return summaries[:limit]


def get_chat_conversation(
    db: Session,
    *,
    current_user: User,
    conversation_id: str,
) -> ChatConversationRead:
    logs = chat_repository.get_conversation_logs(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found",
        )

    first = logs[0]
    last = logs[-1]
    return ChatConversationRead(
        conversation_id=conversation_id,
        title=_build_conversation_title(first.question),
        turn_count=len(logs),
        created_at=first.created_at,
        updated_at=last.created_at,
        messages=[ChatRead.model_validate(log) for log in logs],
    )


def _get_provider(
    provider_name: str | None = None,
    model_name_override: str | None = None,
) -> BaseChatProvider:
    """Resolve the chat provider.

    Per-request ``provider_name`` and ``model_name_override`` take precedence
    over the global ``.env`` values. Passing ``None`` falls back to the
    ``CHAT_PROVIDER`` / provider-specific model env vars.
    """
    effective = (provider_name or settings.CHAT_PROVIDER or "mock").strip().lower()
    if effective == "openai":
        p = OpenAIChatProvider()
        if model_name_override:
            p.model_name = model_name_override.strip()
        return p
    if effective == "deepseek":
        p = DeepSeekChatProvider()
        if model_name_override:
            p.model_name = model_name_override.strip()
        return p
    if effective == "ollama":
        p = OllamaChatProvider()
        if model_name_override:
            p.model_name = model_name_override.strip()
        return p
    if effective == "mock":
        return MockChatProvider()
    raise ChatProviderConfigurationError(
        f"Unsupported CHAT_PROVIDER: {effective}"
    )


def _build_history(db: Session, *, user_id: int, conversation_id: str) -> list[dict[str, str]]:
    logs = chat_repository.get_recent_conversation_logs(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        limit=settings.CHAT_CONTEXT_MAX_TURNS,
    )
    messages: list[dict[str, str]] = []
    for log in logs:
        messages.append({"role": "user", "content": log.question})
        messages.append({"role": "assistant", "content": log.answer})
    return messages


def _build_conversation_title(question: str) -> str:
    title = " ".join(question.strip().split())
    return _truncate_text(title, 40) or "新对话"


def _truncate_text(value: str, max_length: int) -> str:
    text = value.strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
