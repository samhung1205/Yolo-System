"""Public signup can close without disabling login or admin account creation."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, users
from app.core.config import settings
from app.core.deps import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import Base
from app.models import User
from app.services import auth_service

PASSWORD = "Testpass123"
PAYLOAD = {"username":"newmember", "email":"newmember@example.com", "password":PASSWORD, "nickname":"Member"}


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([User(id=1, username="admin1", password_hash=hash_password(PASSWORD), is_admin=True, is_active=True),
                    User(id=2, username="member1", password_hash=hash_password(PASSWORD), is_admin=False, is_active=True)])
        db.commit()
    def connection():
        with factory() as db:
            yield db
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(users.router, prefix="/api/users")
    app.dependency_overrides[get_db] = connection
    auth_service.login_failures.clear()
    with TestClient(app) as client:
        yield client, factory
    auth_service.login_failures.clear()
    engine.dispose()


def test_public_config_exposes_only_policy(site):
    client, _ = site
    response = client.get("/api/auth/config")
    assert response.json() == {"registration_enabled":False}
    assert response.headers["Cache-Control"] == "no-store"


def test_closed_signup_does_not_write_or_hash_password(site, monkeypatch):
    client, factory = site
    def unexpected(*args):
        raise AssertionError("Closed signup must not hash passwords")
    monkeypatch.setattr(auth_service, "hash_password", unexpected)
    response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 403
    with factory() as db:
        assert db.query(User).count() == 2


def test_admin_can_create_account_and_new_account_can_login(site):
    client, factory = site
    headers = {"Authorization":"Bearer " + create_access_token({"sub":"1", "ver":0})}
    response = client.post("/api/users", headers=headers, json=PAYLOAD)
    assert response.status_code == 201
    with factory() as db:
        created = db.query(User).filter(User.username == PAYLOAD["username"]).one()
        assert verify_password(PASSWORD, created.password_hash)
        assert not created.is_admin
    assert client.post("/api/auth/login", json={"username":PAYLOAD["username"], "password":PASSWORD}).status_code == 200


def test_regular_member_cannot_create_accounts(site):
    client, _ = site
    headers = {"Authorization":"Bearer " + create_access_token({"sub":"2", "ver":0})}
    assert client.post("/api/users", headers=headers, json=PAYLOAD).status_code == 403
    assert client.post("/api/users", json=PAYLOAD).status_code == 401


def test_local_signup_can_remain_enabled(site, monkeypatch):
    client, _ = site
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", True)
    assert client.get("/api/auth/config").json() == {"registration_enabled":True}
    assert client.post("/api/auth/register", json=PAYLOAD).status_code == 201
