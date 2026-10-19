"""
LLM access policy: provider/model allowlist, per-user rate limits, and the
route wiring on /api/chat and /api/agent.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.agents import service as agent_service
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agent import AgentChatResponse
from app.services import llm_policy
from app.services.llm_policy import (
    LlmRateLimiter,
    LlmRateLimitExceeded,
    resolve_llm_selection,
)
from main import app


@pytest.fixture(autouse=True)
def _isolate_policy(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr(settings, "OPENAI_ALLOWED_MODELS", [])
    monkeypatch.setattr(settings, "DEEPSEEK_CHAT_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "DEEPSEEK_ALLOWED_MODELS", [])
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(llm_policy, "fetch_ollama_models", lambda: ["qwen3:8b", "llama3.2"])
    llm_policy.llm_rate_limiter.reset()
    yield
    llm_policy.llm_rate_limiter.reset()


# -- allowlist ---------------------------------------------------------------


def test_unknown_provider_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        resolve_llm_selection("anthropic-proxy", None, default_provider="ollama")
    assert exc_info.value.status_code == 400


def test_model_outside_allowlist_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        resolve_llm_selection("openai", "gpt-4", default_provider="ollama")
    assert exc_info.value.status_code == 400


def test_allowlisted_model_is_accepted():
    selection = resolve_llm_selection("openai", "gpt-4o", default_provider="ollama")
    assert (selection.provider, selection.model) == ("openai", "gpt-4o")


def test_configured_allowlist_replaces_builtin_defaults(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_ALLOWED_MODELS", ["gpt-4.1"])
    assert llm_policy.allowed_models("openai") == ["gpt-4.1-mini", "gpt-4.1"]
    with pytest.raises(HTTPException):
        resolve_llm_selection("openai", "gpt-4o", default_provider="ollama")


def test_ollama_only_allows_installed_models():
    assert resolve_llm_selection("ollama", "qwen3:8b:latest", default_provider="ollama").model == "qwen3:8b"
    with pytest.raises(HTTPException):
        resolve_llm_selection("ollama", "not-installed", default_provider="ollama")


def test_switching_provider_without_model_uses_that_providers_default():
    # The agent default model belongs to the default provider; it must not
    # leak into a request that switched provider.
    selection = resolve_llm_selection(
        "deepseek", None, default_provider="ollama", default_model="llama3.2"
    )
    assert (selection.provider, selection.model) == ("deepseek", "deepseek-chat")


def test_default_provider_keeps_its_default_model():
    selection = resolve_llm_selection(None, None, default_provider="ollama", default_model="qwen3:8b")
    assert (selection.provider, selection.model) == ("ollama", "qwen3:8b")


def test_mock_provider_is_blocked_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(HTTPException):
        resolve_llm_selection("mock", None, default_provider="ollama")


# -- rate limiter ------------------------------------------------------------


class _Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_per_minute_window_blocks_then_slides():
    clock = _Clock()
    limiter = LlmRateLimiter(clock=clock)
    for _ in range(3):
        limiter.check_and_record(1, "ollama", per_minute=3, paid_daily=0)

    with pytest.raises(LlmRateLimitExceeded) as exc_info:
        limiter.check_and_record(1, "ollama", per_minute=3, paid_daily=0)
    assert exc_info.value.retry_after_seconds == 60

    # Another user has an independent budget.
    limiter.check_and_record(2, "ollama", per_minute=3, paid_daily=0)

    clock.now += 61
    limiter.check_and_record(1, "ollama", per_minute=3, paid_daily=0)


def test_daily_cap_only_counts_paid_providers():
    clock = _Clock()
    limiter = LlmRateLimiter(clock=clock)
    limiter.check_and_record(1, "openai", per_minute=0, paid_daily=2)
    limiter.check_and_record(1, "deepseek", per_minute=0, paid_daily=2)
    with pytest.raises(LlmRateLimitExceeded):
        limiter.check_and_record(1, "openai", per_minute=0, paid_daily=2)
    # Local models stay usable after the paid budget is spent.
    limiter.check_and_record(1, "ollama", per_minute=0, paid_daily=2)

    clock.now += 86400
    limiter.check_and_record(1, "openai", per_minute=0, paid_daily=2)


def test_rejected_request_does_not_consume_budget():
    limiter = LlmRateLimiter(clock=_Clock())
    limiter.check_and_record(1, "openai", per_minute=5, paid_daily=1)
    for _ in range(3):
        with pytest.raises(LlmRateLimitExceeded):
            limiter.check_and_record(1, "openai", per_minute=5, paid_daily=1)
    # Only the one accepted request counted toward the minute window.
    for _ in range(4):
        limiter.check_and_record(1, "ollama", per_minute=5, paid_daily=1)


# -- route wiring ------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    user = User(id=42, username="tester", is_admin=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None
    calls = []

    def fake_reply(db, **kwargs):
        calls.append(kwargs)
        return AgentChatResponse(conversation_id="c1", answer="ok", mode=kwargs["mode"])

    monkeypatch.setattr(agent_service, "create_agent_reply", fake_reply)
    monkeypatch.setattr(settings, "AGENT_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "AGENT_MODEL", "llama3.2")
    test_client = TestClient(app)
    test_client.calls = calls
    yield test_client
    app.dependency_overrides.clear()


def test_agent_route_rejects_unlisted_model(client):
    response = client.post(
        "/api/agent/chat",
        json={"message": "hi", "provider": "openai", "model": "gpt-4"},
    )
    assert response.status_code == 400
    assert client.calls == []


def test_agent_route_passes_resolved_selection(client):
    response = client.post("/api/agent/chat", json={"message": "hi", "provider": "deepseek"})
    assert response.status_code == 200
    assert client.calls[0]["provider_name"] == "deepseek"
    assert client.calls[0]["model_name_override"] == "deepseek-chat"


def test_agent_route_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_RATE_LIMIT_PER_MINUTE", 1)
    assert client.post("/api/agent/chat", json={"message": "one"}).status_code == 200

    response = client.post("/api/agent/chat", json={"message": "two"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert len(client.calls) == 1


def test_chat_route_rejects_unlisted_model(client):
    response = client.post(
        "/api/chat",
        json={"question": "hi", "provider": "openai", "model": "o1-pro"},
    )
    assert response.status_code == 400
