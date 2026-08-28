"""
Repository helpers for chat logs.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog


def create_log(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
    turn_index: int,
    provider: str,
    model_name: str,
    question: str,
    answer: str,
) -> ChatLog:
    chat_log = ChatLog(
        user_id=user_id,
        conversation_id=conversation_id,
        turn_index=turn_index,
        provider=provider,
        model_name=model_name,
        question=question,
        answer=answer,
    )
    db.add(chat_log)
    db.commit()
    db.refresh(chat_log)
    return chat_log


def list_logs(db: Session, *, user_id: int | None = None, limit: int = 50) -> list[ChatLog]:
    query = db.query(ChatLog)
    if user_id is not None:
        query = query.filter(ChatLog.user_id == user_id)
    return query.order_by(ChatLog.created_at.desc()).limit(limit).all()


def get_conversation_logs(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
) -> list[ChatLog]:
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id, ChatLog.conversation_id == conversation_id)
        .order_by(ChatLog.turn_index.asc(), ChatLog.created_at.asc())
        .all()
    )


def get_recent_conversation_logs(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
    limit: int,
) -> list[ChatLog]:
    rows = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id, ChatLog.conversation_id == conversation_id)
        .order_by(ChatLog.turn_index.desc(), ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def get_next_turn_index(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
) -> int:
    max_turn = (
        db.query(func.max(ChatLog.turn_index))
        .filter(ChatLog.user_id == user_id, ChatLog.conversation_id == conversation_id)
        .scalar()
    )
    if max_turn is None:
        return 1
    return int(max_turn) + 1


def delete_conversation(
    db: Session,
    *,
    user_id: int,
    conversation_id: str,
) -> int:
    deleted_count = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id, ChatLog.conversation_id == conversation_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted_count)
