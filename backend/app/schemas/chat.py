"""
Pydantic schemas for chat requests and responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(default=None, max_length=64)
    provider: Optional[str] = Field(default=None, max_length=32, description="覆蓋 .env CHAT_PROVIDER，例如 openai / deepseek / ollama")
    model: Optional[str] = Field(default=None, max_length=128, description="覆蓋預設模型名稱")

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("問題不可為空")
        return value

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


class ChatRead(BaseModel):
    id: int
    user_id: int
    conversation_id: str
    turn_index: int
    provider: str
    model_name: str
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatConversationSummaryRead(BaseModel):
    conversation_id: str
    title: str
    provider: str
    model_name: str
    turn_count: int
    last_question: str
    last_answer_preview: str
    created_at: datetime
    updated_at: datetime


class ChatConversationRead(BaseModel):
    conversation_id: str
    title: str
    turn_count: int
    created_at: datetime
    updated_at: datetime
    messages: list[ChatRead]
