"""
Auth hardening (security P1): PyJWT tokens with revocation via
users.token_version, failed-login throttling, admin lock-out guard, password
rule, and startup checks. Uses an in-memory SQLite database.
"""
import jwt as pyjwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import startup_checks
from app.core.config import settings
from app.core.deps import resolve_user_from_token
from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.session import Base
from app.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import auth_service, user_service

PASSWORD = "Abc12345"


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    db.add_all(
        [
            User(id=1, username="alice", password_hash=hash_password(PASSWORD), is_admin=False, is_active=True),
            User(id=2, username="root1", password_hash=hash_password(PASSWORD), is_admin=True, is_active=True),
            User(id=3, username="root2", password_hash=hash_password(PASSWORD), is_admin=True, is_active=True),
        ]
    )
    db.commit()
    db.close()
    return factory


@pytest.fixture
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _fresh_throttle():
    auth_service.login_failures.clear()
    yield
    auth_service.login_failures.clear()


# -- tokens ---------------------------------------------------------------------

def test_login_token_carries_version_and_resolves(db):
    token, user = auth_service.login_user(db, "alice", PASSWORD)
    assert decode_access_token(token)["ver"] == 0
    assert resolve_user_from_token(db, token).id == user.id


def test_password_change_revokes_existing_tokens(db):
    token, _ = auth_service.login_user(db, "alice", PASSWORD)
    user_service.update_user(db, 1, UserUpdate(password="Newpass123"))

    assert resolve_user_from_token(db, token) is None
    new_token, _ = auth_service.login_user(db, "alice", "Newpass123")
    assert resolve_user_from_token(db, new_token).username == "alice"


def test_nickname_change_keeps_tokens(db):
    token, _ = auth_service.login_user(db, "alice", PASSWORD)
    user_service.update_user(db, 1, UserUpdate(nickname="A"))
    assert resolve_user_from_token(db, token) is not None


@pytest.mark.parametrize("change", [UserUpdate(is_active=False), UserUpdate(is_admin=True)])
def test_deactivation_or_role_change_revokes(db, change):
    token, _ = auth_service.login_user(db, "alice", PASSWORD)
    user_service.update_user(db, 1, change)
    assert resolve_user_from_token(db, token) is None


def test_pre_migration_token_without_ver_still_valid(db):
    legacy = pyjwt.encode({"sub": "1", "exp": 4102444800}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert resolve_user_from_token(db, legacy).id == 1


def test_tampered_or_unsigned_tokens_rejected(db):
    forged = pyjwt.encode({"sub": "2", "exp": 4102444800}, "not-the-real-signing-key-but-long-enough-0123456789", algorithm="HS256")
    assert resolve_user_from_token(db, forged) is None
    unsigned = pyjwt.encode({"sub": "2", "exp": 4102444800}, None, algorithm="none")
    assert resolve_user_from_token(db, unsigned) is None
    assert decode_access_token(create_access_token({"sub": "1"})) is not None


# -- login throttling -----------------------------------------------------------

def test_account_locks_after_repeated_failures(db, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_ACCOUNT", 3)
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            auth_service.login_user(db, "alice", "wrong", client_ip="1.1.1.1")
        assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        auth_service.login_user(db, "Alice", PASSWORD, client_ip="2.2.2.2")
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0


def test_successful_login_resets_account_counter(db, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_ACCOUNT", 3)
    for _ in range(2):
        with pytest.raises(HTTPException):
            auth_service.login_user(db, "alice", "wrong")
    auth_service.login_user(db, "alice", PASSWORD)
    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            auth_service.login_user(db, "alice", "wrong")
        assert exc.value.status_code == 401


def test_ip_limit_spans_accounts(db, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 2)
    for name in ("ghost1", "ghost2"):
        with pytest.raises(HTTPException):
            auth_service.login_user(db, name, "x", client_ip="9.9.9.9")
    with pytest.raises(HTTPException) as exc:
        auth_service.login_user(db, "alice", PASSWORD, client_ip="9.9.9.9")
    assert exc.value.status_code == 429
    auth_service.login_user(db, "alice", PASSWORD, client_ip="8.8.8.8")


# -- admin lock-out guard ---------------------------------------------------------

def _admin(db, user_id):
    return db.get(User, user_id)


@pytest.mark.parametrize(
    ("user_in", "deleting"),
    [(UserUpdate(is_admin=False), False), (UserUpdate(is_active=False), False), (None, True)],
)
def test_admin_cannot_remove_own_access(db, user_in, deleting):
    with pytest.raises(HTTPException) as exc:
        user_service.guard_admin_change(db, acting_user=_admin(db, 2), target_user_id=2, user_in=user_in, deleting=deleting)
    assert exc.value.status_code == 400


def test_last_active_admin_is_protected(db):
    user_service.guard_admin_change(db, acting_user=_admin(db, 2), target_user_id=3, user_in=UserUpdate(is_admin=False))
    user_service.update_user(db, 3, UserUpdate(is_admin=False))
    # root1 is now the only active admin: nobody may delete or demote it.
    with pytest.raises(HTTPException) as exc:
        user_service.guard_admin_change(db, acting_user=_admin(db, 3), target_user_id=2, deleting=True)
    assert "至少需要保留一位" in exc.value.detail


def test_non_admin_changes_pass_the_guard(db):
    user_service.guard_admin_change(db, acting_user=_admin(db, 2), target_user_id=1, user_in=UserUpdate(is_active=False))


# -- password rule ---------------------------------------------------------------

@pytest.mark.parametrize("password", ["Abc!2345", "p@ssw0rd#Long", "A1" + "x" * 62])
def test_password_rule_accepts_symbols(password):
    UserCreate(username="bob", password=password)


@pytest.mark.parametrize("password", ["abc 12345", "密碼abc123", "abcdefgh", "12345678", "Ab1!", "A1" + "x" * 63])
def test_password_rule_rejects(password):
    with pytest.raises(ValidationError):
        UserCreate(username="bob", password=password)


# -- startup checks --------------------------------------------------------------

@pytest.mark.parametrize(
    ("secret", "has_problem"),
    [
        ("change-me-in-production", True),
        ("change_this_to_a_long_random_string_at_least_32_chars", True),
        ("short-secret", True),
        ("x" * 48, False),
    ],
)
def test_secret_key_check(secret, has_problem):
    assert bool(startup_checks.secret_key_problems(secret)) is has_problem


def test_default_admin_password_detected(session_factory):
    db = session_factory()
    db.add(User(id=9, username="admin", password_hash=hash_password("Admin@2026"), is_admin=True, is_active=True))
    db.commit()
    db.close()
    assert startup_checks.seeded_admin_password_unchanged(session_factory) is True


def test_production_refuses_to_start_with_problems(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "short")
    with pytest.raises(RuntimeError):
        startup_checks.run_startup_checks(settings, session_factory)


def test_development_only_warns(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "SECRET_KEY", "short")
    assert startup_checks.run_startup_checks(settings, session_factory)
