"""
Agent API routes — Phase 6A-1.

Exposes the LangGraph-backed agent assistant alongside the existing
``/api/chat`` endpoints. The agent route is deliberately a separate prefix
(``/api/agent``) so the deterministic chat pipeline remains unaffected.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents import service as agent_service
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentModeRead

router = APIRouter()


AGENT_MODES: list[AgentModeRead] = [
    AgentModeRead(
        key="auto",
        label="自動偵測",
        description="由 supervisor 依使用者訊息自動判斷該執行哪個 agent 模式。",
        admin_only=False,
    ),
    AgentModeRead(
        key="general_chat",
        label="一般對話",
        description="使用 agent 進行一般性對話，不會主動查詢資料庫。",
        admin_only=False,
    ),
    AgentModeRead(
        key="explain_detection",
        label="解釋偵測結果",
        description="搭配 detection_id，解釋指定的 YOLO 偵測結果。",
        admin_only=False,
    ),
    AgentModeRead(
        key="history_analysis",
        label="偵測歷史分析",
        description="統計使用者的偵測任務數量、狀態與常見類別。",
        admin_only=False,
    ),
    AgentModeRead(
        key="report",
        label="產出報告",
        description="搭配 detection_id，輸出 markdown 報告與解讀。",
        admin_only=False,
    ),
    AgentModeRead(
        key="admin_help",
        label="管理員輔助",
        description="管理員專用：摘要使用者與系統使用情況。",
        admin_only=True,
    ),
]


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(
    payload: AgentChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentChatResponse:
    """Run a single agent turn and persist it to ``chat_logs``."""
    return agent_service.create_agent_reply(
        db,
        current_user=current_user,
        message=payload.message,
        conversation_id=payload.conversation_id,
        mode=payload.mode or "auto",
        detection_id=payload.detection_id,
        provider_name=payload.provider,
        model_name_override=payload.model,
    )


@router.post("/chat/stream")
def stream_agent_chat(
    payload: AgentChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """SSE stream for a single agent turn.

    Emits ``start`` → one or more ``chunk`` → ``done`` (or ``error``).
    The final turn is also persisted to ``chat_logs`` at the ``done`` event.
    """
    return StreamingResponse(
        agent_service.stream_agent_reply(
            db,
            current_user=current_user,
            message=payload.message,
            conversation_id=payload.conversation_id,
            mode=payload.mode or "auto",
            detection_id=payload.detection_id,
            provider_name=payload.provider,
            model_name_override=payload.model,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/modes", response_model=list[AgentModeRead])
def list_agent_modes() -> list[AgentModeRead]:
    """Return the supported agent modes, including ``admin_only`` flags."""
    return AGENT_MODES
