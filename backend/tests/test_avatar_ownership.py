"""
Avatar ownership and cleanup: uploads are named after the uploader, only the
uploader may assign them, and files nothing references are deleted.
Uses an in-memory SQLite database and a temporary avatar directory.
"""
import io
import os
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_admin, get_current_user, get_db
from app.core.security import hash_password
from app.db.session import Base
from app.models import User
from app.schemas.user import UserUpdate
from app.services import avatar_service, user_service
from main import app
from scripts import cleanup_avatars

OLD = time.time() - 2 * avatar_service.PENDING_UPLOAD_TTL_SECONDS
LAST_WEEK = time.time() - 7 * 86400


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    db.add_all(
        [
            User(id=1, username="alice", password_hash=hash_password("Abc12345"), is_active=True),
            User(id=2, username="bob", password_hash=hash_password("Abc12345"), is_active=True),
            User(id=9, username="root", password_hash=hash_password("Abc12345"), is_admin=True, is_active=True),
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
def avatar_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(avatar_service, "AVATAR_DIR", tmp_path)
    return tmp_path


def _file(avatar_dir, name, *, mtime=None):
    path = avatar_dir / name
    path.write_bytes(b"img")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return name


def _png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    return buffer.getvalue()


# -- assignment rules -------------------------------------------------------------

def test_own_upload_can_be_assigned(db, avatar_dir):
    name = _file(avatar_dir, "u1_20261020120000_aaaaaaaa.png")
    avatar_service.check_avatar_assignment(db, acting_user_id=1, filename=name, target_user=db.get(User, 1))


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("u2_20261020120000_aaaaaaaa.png", avatar_service.INVALID_AVATAR_MESSAGE),
        ("20261020120000_aaaaaaaa.png", avatar_service.INVALID_AVATAR_MESSAGE),
        ("u1_20261020120000_bbbbbbbb.png", avatar_service.MISSING_AVATAR_MESSAGE),
    ],
)
def test_foreign_legacy_or_missing_upload_is_rejected(db, avatar_dir, name, message):
    _file(avatar_dir, "u2_20261020120000_aaaaaaaa.png")
    _file(avatar_dir, "20261020120000_aaaaaaaa.png")
    with pytest.raises(HTTPException) as exc:
        avatar_service.check_avatar_assignment(db, acting_user_id=1, filename=name, target_user=db.get(User, 1))
    assert exc.value.detail == message


def test_file_used_by_another_account_is_rejected(db, avatar_dir):
    name = _file(avatar_dir, "u9_20261020120000_aaaaaaaa.png")
    db.get(User, 2).avatar = name
    db.commit()
    with pytest.raises(HTTPException) as exc:
        avatar_service.check_avatar_assignment(db, acting_user_id=9, filename=name, target_user=db.get(User, 1))
    assert exc.value.detail == avatar_service.AVATAR_IN_USE_MESSAGE


def test_resending_current_legacy_avatar_is_allowed(db):
    user = db.get(User, 1)
    user.avatar = "20250101000000_abcdef01.jpg"
    db.commit()
    avatar_service.check_avatar_assignment(db, acting_user_id=1, filename=user.avatar, target_user=user)


# -- cleanup ---------------------------------------------------------------------

def test_switching_avatar_deletes_previous_file(db, avatar_dir):
    first = _file(avatar_dir, "u1_20261020120000_aaaaaaaa.png")
    second = _file(avatar_dir, "u1_20261020130000_bbbbbbbb.png")
    user_service.update_user(db, 1, UserUpdate(avatar=first))
    user_service.update_user(db, 1, UserUpdate(avatar=second))
    assert not (avatar_dir / first).exists()
    assert (avatar_dir / second).exists()


def test_previous_file_kept_while_another_account_uses_it(db, avatar_dir):
    shared = _file(avatar_dir, "20250101000000_abcdef01.jpg")
    for user_id in (1, 2):
        db.get(User, user_id).avatar = shared
    db.commit()
    user_service.update_user(db, 1, UserUpdate(avatar=_file(avatar_dir, "u1_20261020120000_aaaaaaaa.png")))
    assert (avatar_dir / shared).exists()


def test_nickname_change_keeps_avatar(db, avatar_dir):
    name = _file(avatar_dir, "u1_20261020120000_aaaaaaaa.png")
    user_service.update_user(db, 1, UserUpdate(avatar=name))
    user_service.update_user(db, 1, UserUpdate(nickname="A"))
    assert (avatar_dir / name).exists()


def test_deleting_user_removes_avatar_and_pending_uploads(db, avatar_dir):
    current = _file(avatar_dir, "u1_20261020120000_aaaaaaaa.png")
    pending = _file(avatar_dir, "u1_20261020130000_bbbbbbbb.png")
    others = _file(avatar_dir, "u2_20261020120000_cccccccc.png")
    user_service.update_user(db, 1, UserUpdate(avatar=current))
    user_service.delete_user(db, 1)
    assert not (avatar_dir / current).exists()
    assert not (avatar_dir / pending).exists()
    assert (avatar_dir / others).exists()


def test_prune_only_touches_old_unassigned_uploads_of_that_user(db, avatar_dir):
    old_pending = _file(avatar_dir, "u1_20261020100000_aaaaaaaa.png", mtime=OLD)
    fresh_pending = _file(avatar_dir, "u1_20261020120000_bbbbbbbb.png")
    old_in_use = _file(avatar_dir, "u1_20261020090000_cccccccc.png", mtime=OLD)
    other_user = _file(avatar_dir, "u2_20261020100000_dddddddd.png", mtime=OLD)
    prefix_lookalike = _file(avatar_dir, "u11_20261020100000_eeeeeeee.png", mtime=OLD)
    db.get(User, 2).avatar = old_in_use
    db.commit()

    removed = avatar_service.prune_pending_uploads(db, 1)

    assert removed == [old_pending]
    for kept in (fresh_pending, old_in_use, other_user, prefix_lookalike):
        assert (avatar_dir / kept).exists()


# -- routes ----------------------------------------------------------------------

@pytest.fixture
def client(session_factory):
    acting = {"user_id": 1}

    def _db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def _user():
        session = session_factory()
        user = session.get(User, acting["user_id"])
        session.close()
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_current_admin] = _user
    test_client = TestClient(app)
    test_client.acting = acting
    yield test_client
    app.dependency_overrides.clear()


def test_upload_names_file_after_uploader_and_prunes_old_uploads(client, avatar_dir):
    stale = _file(avatar_dir, "u1_20261020100000_aaaaaaaa.png", mtime=OLD)
    response = client.post("/api/upload/avatar", files={"file": ("me.png", _png_bytes(), "image/png")})
    assert response.status_code == 200
    filename = response.json()["filename"]
    assert avatar_service.uploader_of(filename) == 1
    assert (avatar_dir / filename).exists()
    assert not (avatar_dir / stale).exists()

    assert client.put("/api/auth/profile", json={"avatar": filename}).status_code == 200


def test_user_cannot_claim_another_users_upload(client):
    client.acting["user_id"] = 2
    filename = client.post(
        "/api/upload/avatar", files={"file": ("b.png", _png_bytes(), "image/png")}
    ).json()["filename"]
    client.acting["user_id"] = 1
    response = client.put("/api/auth/profile", json={"avatar": filename})
    assert response.status_code == 400


def test_admin_assigns_own_upload_to_another_account(client, session_factory):
    client.acting["user_id"] = 9
    filename = client.post(
        "/api/upload/avatar", files={"file": ("a.png", _png_bytes(), "image/png")}
    ).json()["filename"]
    response = client.put("/api/users/2", json={"avatar": filename})
    assert response.status_code == 200
    db = session_factory()
    assert db.get(User, 2).avatar == filename
    db.close()


# -- sweep script ----------------------------------------------------------------

def test_cleanup_script_dry_run_then_apply(session_factory, avatar_dir, capsys):
    db = session_factory()
    used = _file(avatar_dir, "20250101000000_abcdef01.jpg", mtime=LAST_WEEK)
    orphan = _file(avatar_dir, "20250101000000_00000000.jpg", mtime=LAST_WEEK)
    recent = _file(avatar_dir, "u2_20261020120000_aaaaaaaa.png", mtime=OLD)  # younger than the 24h default
    db.get(User, 1).avatar = used
    db.commit()
    db.close()

    assert cleanup_avatars.main([], session_factory=session_factory) == 0
    assert (avatar_dir / orphan).exists()
    assert orphan in capsys.readouterr().out

    assert cleanup_avatars.main(["--apply"], session_factory=session_factory) == 0
    assert not (avatar_dir / orphan).exists()
    assert (avatar_dir / used).exists()
    assert (avatar_dir / recent).exists()
