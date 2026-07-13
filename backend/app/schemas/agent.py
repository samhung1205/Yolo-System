"""
Pydantic schemas for the agentic API (`/api/agent/*`).

Phase 6A-1 keeps the schema intentionally small. The agent layer reuses the
existing ``chat_logs`` table (with ``provider="langgraph-agent"``) so no new
persisted entities are required at the API surface.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


ALLOWED_AGENT_MODES = {
    "auto",
    "general_chat",
    "explain_detection",
    "history_analysis",
    "report",
    "admin_help",
}


class AgentChatRequest(BaseModel):
    """Request payload for ``POST /api/agent/chat``."""

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(default=None, max_length=64)
    mode: Optional[str] = Field(default="auto", max_length=32)
    detection_id: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = Field(
        default=False,
        description="Reserved for Phase 6A-2; streaming is not implemented yet.",
    )
    provider: Optional[str] = Field(
        default=None,
        max_length=32,
        description="覆蓋 AGENT_PROVIDER，例如 openai / deepseek / ollama",
    )
    model: Optional[str] = Field(
        default=None,
        max_length=128,
        description="覆蓋預設 agent 模型名稱",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("訊息不可為空")
        return text

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip()
        return text or None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> str:
        if v is None or not v.strip():
            return "auto"
        text = v.strip().lower()
        if text not in ALLOWED_AGENT_MODES:
            raise ValueError(
                f"mode 必須是以下之一：{sorted(ALLOWED_AGENT_MODES)}"
            )
        return text

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        allowed = {"openai", "deepseek", "ollama", "mock"}
        if cleaned and cleaned not in allowed:
            raise ValueError(f"provider 必須是 {sorted(allowed)} 之一")
        return cleaned or None


class AgentChatResponse(BaseModel):
    """Response payload for ``POST /api/agent/chat``."""

    conversation_id: str
    answer: str
    mode: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    references: Optional[list[dict[str, Any]]] = None
    success: bool = True
    errors: list[str] = Field(default_factory=list)


class AgentModeRead(BaseModel):
    """Single agent mode descriptor returned by ``GET /api/agent/modes``."""

    key: str
    label: str
    description: str
    admin_only: bool = False
