"""Agent graph: one compiled graph for invoke + stream, history in every mode,
and explicit (non-mock) failures."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents import graph, llm
from app.agents.llm import (
    AgentLLMConfigurationError,
    AgentLLMInvocationError,
    AgentLLMResponse,
    MockChatModel,
)
from app.core.config import settings

USER = SimpleNamespace(id=1, username="tester", is_admin=False)
HISTORY = [
    {"role": "user", "content": "第一個物件是什麼？"},
    {"role": "assistant", "content": "是一艘船。"},
]


class _ScriptedModel:
    """Streams fixed chunks and records the messages it was given."""

    provider = "test"
    model_name = "test-model"

    def __init__(self, chunks=("你", "好")) -> None:
        self.chunks = chunks
        self.messages = None

    def stream(self, messages):
        self.messages = messages
        for chunk in self.chunks:
            yield AgentLLMResponse(content=chunk, provider=self.provider, model_name=self.model_name)


class _FailingModel:
    provider = "test"
    model_name = "test-model"

    def stream(self, _messages):
        raise AgentLLMInvocationError("provider unavailable")
        yield  # pragma: no cover


def _kwargs(**overrides):
    base = dict(
        db=None,
        current_user=USER,
        message="hello",
        history_messages=[],
        conversation_id="c1",
        mode="general_chat",
        detection_id=None,
    )
    base.update(overrides)
    return base


def test_graph_is_compiled_once():
    assert graph._get_compiled_graph() is graph._get_compiled_graph()


def test_invoke_and_stream_share_the_same_answer(monkeypatch):
    monkeypatch.setattr(graph, "get_chat_model", lambda **_: _ScriptedModel())

    invoked = graph.run_graph(**_kwargs())
    events = list(graph.stream_graph(**_kwargs()))

    phases = [phase for phase, _ in events]
    assert phases == ["ready", "answer_chunk", "answer_chunk", "done"]
    streamed = "".join(data for phase, data in events if phase == "answer_chunk")
    assert streamed == invoked["final_answer"] == "你好"
    assert events[-1][1]["final_answer"] == "你好"


def test_general_chat_keeps_history_after_system_prompts(monkeypatch):
    model = _ScriptedModel()
    monkeypatch.setattr(graph, "get_chat_model", lambda **_: model)

    graph.run_graph(**_kwargs(history_messages=HISTORY))

    assert [m["role"] for m in model.messages] == ["system", "system", "user", "assistant", "user"]


def test_explain_mode_now_carries_history_and_runtime_context(monkeypatch):
    model = _ScriptedModel()
    seen = {}
    monkeypatch.setattr(graph, "get_chat_model", lambda **_: model)

    def fake_explainer(db, *, current_user, detection_id):
        seen.update(db=db, user=current_user, detection_id=detection_id)
        return {"ok": True, "detection_id": detection_id, "detail": {}, "stats": {}, "image": None}

    monkeypatch.setattr(graph.subagents, "run_yolo_explainer", fake_explainer)
    sentinel_db = object()

    result = graph.run_graph(
        **_kwargs(
            db=sentinel_db,
            mode="explain_detection",
            detection_id=12,
            message="那第二個物件呢？",
            history_messages=HISTORY,
        )
    )

    assert result["errors"] == []
    assert seen == {"db": sentinel_db, "user": USER, "detection_id": 12}
    roles = [m["role"] for m in model.messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert "那第二個物件呢？" in model.messages[-1]["content"]


def test_report_header_is_streamed_before_llm_text(monkeypatch):
    monkeypatch.setattr(graph, "get_chat_model", lambda **_: _ScriptedModel(chunks=("summary",)))
    monkeypatch.setattr(
        graph.subagents,
        "run_report_agent",
        lambda db, **kw: {"ok": True, "markdown": "# Report", "image": None},
    )
    monkeypatch.setattr(graph.subagents, "build_report_agent_messages", lambda *_: [{"role": "user", "content": "x"}])

    events = list(graph.stream_graph(**_kwargs(mode="report", detection_id=3)))

    chunks = [data for phase, data in events if phase == "answer_chunk"]
    assert chunks == ["# Report\n\n---\n\n", "summary"]
    assert events[-1][1]["final_answer"] == "# Report\n\n---\n\nsummary"


def test_llm_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(graph, "get_chat_model", lambda **_: _FailingModel())

    result = graph.run_graph(**_kwargs())
    assert result["errors"] == ["llm_invocation_failed"]
    assert result["final_answer"] == graph.LLM_FAILED_MESSAGE

    events = list(graph.stream_graph(**_kwargs()))
    assert events[-1] == ("error", graph.LLM_FAILED_MESSAGE)


def test_missing_api_key_is_reported_instead_of_mock_answer(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    with pytest.raises(AgentLLMConfigurationError):
        llm.get_chat_model(provider="openai", model_name="gpt-4.1-mini")

    result = graph.run_graph(**_kwargs(provider_name="openai", model_name_override="gpt-4.1-mini"))
    assert result["errors"] == ["llm_not_configured"]
    assert "mock" not in result["final_answer"]


def test_explicit_mock_provider_still_works():
    result = graph.run_graph(**_kwargs(provider_name="mock", model_name_override="mock-chat"))
    assert result["errors"] == []
    assert "[mock-agent]" in result["final_answer"]


def test_tool_errors_stream_as_error_event(monkeypatch):
    events = list(graph.stream_graph(**_kwargs(mode="explain_detection", detection_id=None)))
    assert events[0][0] == "ready"
    assert events[-1] == ("error", "請提供有效的 detection_id 才能解釋 YOLO 結果。")


def test_stream_failure_mid_answer_does_not_resend_full_answer():
    class _Chunk:
        def __init__(self, content):
            self.content = content

    class _BrokenLangChainModel:
        def __init__(self):
            self.invoked = False

        def stream(self, _messages):
            yield _Chunk("partial")
            raise RuntimeError("connection reset")

        def invoke(self, _messages):  # pragma: no cover - must not be called
            self.invoked = True
            return _Chunk("full answer")

    inner = _BrokenLangChainModel()
    wrapper = llm._LangChainChatModel(inner, provider="ollama", model_name="qwen2.5")

    received = []
    with pytest.raises(AgentLLMInvocationError):
        for chunk in wrapper.stream([{"role": "user", "content": "hi"}]):
            received.append(chunk.content)

    assert received == ["partial"]
    assert inner.invoked is False


def test_mock_model_streams_words():
    chunks = list(MockChatModel().stream([{"role": "user", "content": "hi"}]))
    assert len(chunks) > 1
