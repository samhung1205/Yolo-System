"""
SSE contract of POST /api/agent/chat/stream (consumed by AgentPage.jsx and
the desktop AgentWindow): start -> chunk... -> done, and chunks add up to the
final answer.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.agents import service as agent_service
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services import llm_policy
from main import app


@pytest.fixture
def client(monkeypatch):
    user = User(id=3, username="streamer", is_admin=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None
    saved = []
    monkeypatch.setattr(agent_service, "_build_history_messages", lambda *_, **__: [])
    monkeypatch.setattr(agent_service.chat_repository, "get_next_turn_index", lambda *_, **__: 1)
    monkeypatch.setattr(agent_service.chat_repository, "create_log", lambda *_, **kw: saved.append(kw))
    llm_policy.llm_rate_limiter.reset()
    test_client = TestClient(app)
    test_client.saved = saved
    yield test_client
    app.dependency_overrides.clear()


def _events(response):
    return [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_stream_emits_start_chunks_done(client):
    response = client.post(
        "/api/agent/chat/stream",
        json={"message": "hi", "mode": "general_chat", "provider": "mock"},
    )
    assert response.status_code == 200

    events = _events(response)
    assert events[0]["type"] == "start"
    assert events[0]["tool_calls"] == [{"tool": "general_chat", "ok": True}]
    assert events[-1]["type"] == "done"
    chunks = "".join(e["delta"] for e in events if e["type"] == "chunk")
    assert chunks.strip() == events[-1]["answer"]
    assert client.saved[0]["answer"] == events[-1]["answer"]


def test_stream_reports_missing_detection_as_error(client):
    response = client.post(
        "/api/agent/chat/stream",
        json={"message": "explain", "mode": "explain_detection", "provider": "mock"},
    )
    events = _events(response)
    assert [e["type"] for e in events] == ["start", "error"]
    assert client.saved == []


def test_tool_engine_streams_tool_events(client, monkeypatch):
    from langchain_core.messages import AIMessage

    from app.agents import langchain_tools, tool_agent
    from app.core.config import settings
    from fake_models import ScriptedToolModel

    monkeypatch.setattr(settings, "AGENT_ENGINE", "tool_calling")
    tool_agent._agent_cache.clear()
    model = ScriptedToolModel(
        script=[
            AIMessage(content="", tool_calls=[{"name": "summarize_detection_history", "args": {}, "id": "c1"}]),
            AIMessage(content="共 3 筆偵測。"),
        ]
    )
    monkeypatch.setattr(tool_agent, "get_chat_model", lambda **_: type("W", (), {"langchain_model": model})())
    monkeypatch.setattr(
        langchain_tools,
        "summarize_detection_history_tool",
        lambda db, **_: {"ok": True, "total_tasks": 3},
    )

    response = client.post(
        "/api/agent/chat/stream",
        json={"message": "我有幾筆偵測？", "mode": "history_analysis", "provider": "ollama", "model": "qwen2.5"},
    )
    events = _events(response)
    tool_agent._agent_cache.clear()

    types = [e["type"] for e in events]
    assert types[0] == "start" and types[-1] == "done"
    assert {"type": "tool", "tool": "summarize_detection_history", "status": "done", "ok": True} in events
    assert events[-1]["answer"] == "共 3 筆偵測。"
    assert events[-1]["tool_calls"] == [{"tool": "summarize_detection_history", "ok": True}]
