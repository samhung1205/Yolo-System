"""
Chat log ORM model for persisted AI chat records.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"
    # Migration 0013; chat_repository.append_log retries on a collision.
    __table_args__ = (
        UniqueConstraint("user_id", "conversation_id", "turn_index", name="uq_chat_logs_user_conversation_turn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<ChatLog id={self.id} user_id={self.user_id} "
            f"conversation_id={self.conversation_id} turn_index={self.turn_index}>"
        )
