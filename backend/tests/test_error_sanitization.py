"""
Internal exception text (upstream bodies, paths, key hints) must never reach
API clients; it belongs in the server log only.
"""
import json

import pytest
from fastapi import HTTPException

from app.agents import graph
from app.integrations.chat_providers.base import ChatProviderRequestError
from app.models.user import User
from app.services import chat_service

SECRET = "Incorrect API key provided: sk-live-abc123 at /Users/someone/backend"


class _FailingProvider:
    provider_name = "openai"
    model_name = "gpt-4.1-mini"

    def chat(self, question, *, history=None):
        raise ChatProviderRequestError(SECRET)

    def stream_chat(self, question, *, history=None):
        raise ChatProviderRequestError(SECRET)


def test_chat_reply_hides_provider_error(monkeypatch):
    monkeypatch.setattr(chat_service, "_get_provider", lambda **_: _FailingProvider())
    monkeypatch.setattr(chat_service, "_build_history", lambda *_, **__: [])

    with pytest.raises(HTTPException) as exc_info:
        chat_service.create_chat_reply(
            None,
            current_user=User(id=1, username="u"),
            question="hi",
        )

    assert exc_info.value.status_code == 502
    assert "sk-" not in exc_info.value.detail
    assert "/Users/" not in exc_info.value.detail


def test_chat_stream_hides_unexpected_error(monkeypatch):
    def boom(**_):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(chat_service, "_get_provider", boom)

    events = list(chat_service.stream_chat_reply(user_id=1, question="hi"))

    payload = json.loads(events[-1].removeprefix("data: ").strip())
    assert payload["type"] == "error"
    assert "sk-" not in payload["message"]


def test_agent_error_node_does_not_echo_unknown_errors():
    state = graph._handle_error_node({"errors": [f"unexpected error: {SECRET}"]})
    assert "sk-" not in state["final_answer"]
    assert "/Users/" not in state["final_answer"]


def test_agent_tool_failure_is_reported_as_code(monkeypatch):
    from app.agents.tools import history_tools

    def explode(*_, **__):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(history_tools.detection_repository, "list_tasks", explode)

    result = history_tools.list_recent_detections_tool(
        None,
        current_user=User(id=1, username="u", is_admin=False),
    )
    assert result == {"ok": False, "error": "internal_error"}
