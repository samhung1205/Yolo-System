"""
Self-service profile endpoint (PUT /api/auth/profile): the desktop app now
uses it for nickname / avatar / password, and a password change requires the
current password.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.core.deps import get_current_user, get_db
from app.core.security import hash_password
from app.models.user import User
from main import app

AVATAR = "20261019120000_ab12cd34.png"


@pytest.fixture
def client(tmp_path, monkeypatch):
    user = User(
        id=7,
        username="tester",
        nickname="old",
        password_hash=hash_password("Abc12345"),
        is_admin=False,
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None

    calls = []

    def fake_update_user(db, user_id, update):
        calls.append((user_id, update))
        return user

    monkeypatch.setattr(auth_routes.user_service, "update_user", fake_update_user)
    monkeypatch.setattr(
        auth_routes,
        "to_user_read",
        lambda u: {
            "id": u.id,
            "username": u.username,
            "email": None,
            "nickname": u.nickname,
            "avatar": None,
            "register_time": "2026-10-19T00:00:00",
            "is_admin": False,
            "is_active": True,
        },
    )
    monkeypatch.setattr(auth_routes, "AVATAR_DIR", tmp_path)

    test_client = TestClient(app)
    test_client.calls = calls
    test_client.avatar_dir = tmp_path
    yield test_client
    app.dependency_overrides.clear()


def test_password_change_requires_current_password(client):
    response = client.put("/api/auth/profile", json={"password": "Newpass123"})
    assert response.status_code == 400
    assert client.calls == []


def test_password_change_rejects_wrong_current_password(client):
    response = client.put(
        "/api/auth/profile",
        json={"password": "Newpass123", "current_password": "Wrong1234"},
    )
    assert response.status_code == 400
    assert client.calls == []


def test_password_change_with_current_password(client):
    response = client.put(
        "/api/auth/profile",
        json={"password": "Newpass123", "current_password": "Abc12345"},
    )
    assert response.status_code == 200
    user_id, update = client.calls[0]
    assert user_id == 7
    assert update.password == "Newpass123"


def test_nickname_only_update_needs_no_password(client):
    response = client.put("/api/auth/profile", json={"nickname": "new"})
    assert response.status_code == 200
    assert client.calls[0][1].nickname == "new"


def test_avatar_must_look_like_an_uploaded_filename(client):
    response = client.put("/api/auth/profile", json={"avatar": "../../etc/passwd"})
    assert response.status_code == 422
    assert client.calls == []


def test_avatar_must_exist(client):
    response = client.put("/api/auth/profile", json={"avatar": AVATAR})
    assert response.status_code == 400
    assert client.calls == []


def test_avatar_update(client):
    (client.avatar_dir / AVATAR).write_bytes(b"png")
    response = client.put("/api/auth/profile", json={"avatar": AVATAR})
    assert response.status_code == 200
    assert client.calls[0][1].avatar == AVATAR
