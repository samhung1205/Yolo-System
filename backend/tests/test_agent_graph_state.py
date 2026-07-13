"""Regression tests for LangGraph state and explicit LLM failures."""
from __future__ import annotations

from types import SimpleNamespace

from app.agents import graph
from app.agents.llm import AgentLLMInvocationError, AgentLLMResponse


class _CapturingModel:
    provider = "test"
    model_name = "test-model"

    def __init__(self) -> None:
        self.messages = []

    def invoke(self, messages):
        self.messages = messages
        return AgentLLMResponse(
            content="ok",
            provider=self.provider,
            model_name=self.model_name,
        )


class _FailingModel:
    provider = "test"
    model_name = "test-model"

    def invoke(self, _messages):
        raise AgentLLMInvocationError("provider unavailable")


def _state():
    user = SimpleNamespace(id=1, username="tester", is_admin=False)
    return graph._build_state(
        user=user,
        message="hello",
        history_messages=[],
        conversation_id="test-conversation",
        mode="general_chat",
        detection_id=None,
    ), user


def test_langgraph_preserves_composed_llm_messages(monkeypatch) -> None:
    state, user = _state()
    model = _CapturingModel()
    monkeypatch.setattr(graph, "get_chat_model", lambda **_kwargs: model)

    result = graph._build_langgraph_app(None, user).invoke(state)

    assert result["final_answer"] == "ok"
    assert [message["role"] for message in model.messages] == [
        "system",
        "system",
        "user",
    ]


def test_llm_failure_is_explicit_and_not_agent_error_text(monkeypatch) -> None:
    state, _user = _state()
    state = graph._classify_intent_node(state)
    state = graph._call_tools_or_subagent_node(
        state,
        db=None,
        current_user=SimpleNamespace(id=1, username="tester", is_admin=False),
    )
    monkeypatch.setattr(graph, "get_chat_model", lambda **_kwargs: _FailingModel())

    result = graph._compose_answer_node(state)

    assert result["errors"] == ["llm_invocation_failed"]
    assert "[agent-error]" not in result["final_answer"]
