"""
chat_logs turn_index uniqueness (migration 0013): the constraint rejects a
duplicate turn, append_log retries with the next index, and the migration
renumbers existing duplicates. Uses an in-memory SQLite database.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.session import Base
from app.models import ChatLog, User
from app.repositories import chat_repository

MIGRATION = Path(__file__).resolve().parents[1] / "migrations/versions/20261020_0013_chat_logs_unique_turn_index.py"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add_all(
        [
            User(id=1, username="alice", password_hash=hash_password("Abc12345"), is_active=True),
            User(id=2, username="bob", password_hash=hash_password("Abc12345"), is_active=True),
        ]
    )
    session.commit()
    yield session
    session.close()


def _log(db, *, user_id=1, conversation_id="c1", turn_index=1, question="q"):
    return chat_repository.create_log(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_index=turn_index,
        provider="mock",
        model_name="mock-chat",
        question=question,
        answer="a",
    )


def _append(db, **kwargs):
    defaults = dict(user_id=1, conversation_id="c1", provider="mock", model_name="mock-chat", question="q", answer="a")
    return chat_repository.append_log(db, **{**defaults, **kwargs})


def test_duplicate_turn_is_rejected(db):
    _log(db)
    with pytest.raises(IntegrityError):
        _log(db)


def test_same_turn_number_allowed_across_users_and_conversations(db):
    _log(db)
    _log(db, conversation_id="c2")
    _log(db, user_id=2)


def test_append_numbers_turns_in_order(db):
    assert [_append(db).turn_index for _ in range(3)] == [1, 2, 3]
    assert _append(db, conversation_id="other").turn_index == 1


def test_append_retries_when_another_request_took_the_index(db, monkeypatch):
    _log(db)
    real_next = chat_repository.get_next_turn_index
    stale = iter([1])  # the first read is stale, as if a parallel request won the race

    def next_index(db, **kwargs):
        return next(stale, None) or real_next(db, **kwargs)

    monkeypatch.setattr(chat_repository, "get_next_turn_index", next_index)
    assert _append(db, question="second").turn_index == 2


def test_append_gives_up_after_max_attempts(db, monkeypatch):
    _log(db)
    monkeypatch.setattr(chat_repository, "get_next_turn_index", lambda db, **kwargs: 1)
    with pytest.raises(IntegrityError):
        _append(db)


def test_migration_renumbers_duplicates_in_order():
    spec = importlib.util.spec_from_file_location("migration_0013", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE chat_logs (id INTEGER PRIMARY KEY, user_id INTEGER, conversation_id TEXT, "
                "turn_index INTEGER, created_at TEXT)"
            )
        )
        conn.execute(
            text("INSERT INTO chat_logs VALUES (:id, :u, :c, :t, :at)"),
            [
                {"id": 1, "u": 1, "c": "c1", "t": 1, "at": "2026-01-01 10:00"},
                {"id": 2, "u": 1, "c": "c1", "t": 2, "at": "2026-01-01 10:01"},
                {"id": 3, "u": 1, "c": "c1", "t": 2, "at": "2026-01-01 10:02"},  # duplicate
                {"id": 4, "u": 1, "c": "c1", "t": 3, "at": "2026-01-01 10:03"},
                {"id": 5, "u": 2, "c": "c1", "t": 1, "at": "2026-01-01 10:00"},  # other user
            ],
        )
        changed = migration._renumber_turns(conn)
        rows = conn.execute(text("SELECT id, turn_index FROM chat_logs ORDER BY id")).fetchall()

    assert changed == 2
    assert [tuple(row) for row in rows] == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 1)]


def test_model_declares_the_constraint():
    names = {c.name for c in ChatLog.__table__.constraints}
    assert "uq_chat_logs_user_conversation_turn" in names
