"""
Chat API routes.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import ChatConversationRead, ChatConversationSummaryRead, ChatRead, ChatRequest
from app.services import chat_service
from app.services.llm_policy import LlmSelection, authorize_llm_request

router = APIRouter()


def _authorize(payload: ChatRequest, current_user: User) -> LlmSelection:
    return authorize_llm_request(
        user_id=current_user.id,
        provider_override=payload.provider,
        model_override=payload.model,
        default_provider=settings.CHAT_PROVIDER,
    )


@router.post("", response_model=ChatRead, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    selection = _authorize(payload, current_user)
    return chat_service.create_chat_reply(
        db,
        current_user=current_user,
        question=payload.question,
        conversation_id=payload.conversation_id,
        provider_name=selection.provider,
        model_name_override=selection.model,
    )


@router.post("/stream")
def stream_chat(
    payload: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    selection = _authorize(payload, current_user)
    return StreamingResponse(
        chat_service.stream_chat_reply(
            user_id=current_user.id,
            question=payload.question,
            conversation_id=payload.conversation_id,
            provider_name=selection.provider,
            model_name_override=selection.model,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=list[ChatConversationSummaryRead])
def list_chat_conversations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=100),
):
    return chat_service.list_chat_conversations(
        db,
        current_user=current_user,
        limit=limit,
    )


@router.get("/{conversation_id}", response_model=ChatConversationRead)
def get_chat_conversation(
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return chat_service.get_chat_conversation(
        db,
        current_user=current_user,
        conversation_id=conversation_id,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_conversation(
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    chat_service.delete_chat_conversation(
        db,
        current_user=current_user,
        conversation_id=conversation_id,
    )
