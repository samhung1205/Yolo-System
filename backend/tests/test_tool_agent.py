"""Tool-calling engine (AGENT_ENGINE=tool_calling): engine selection, tool
scoping through runtime context, streamed phases, and pipeline-equivalent
errors."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from fake_models import ScriptedToolModel
from app.agents import langchain_tools, tool_agent
from app.agents.langchain_tools import AgentToolContext
from app.core.config import settings

USER = SimpleNamespace(id=4, username="u", is_admin=False)
ADMIN = SimpleNamespace(id=1, username="admin", is_admin=True)


def _call(name, args=None, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])


@pytest.fixture(autouse=True)
def _engine(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_ENGINE", "tool_calling")
    monkeypatch.setattr(settings, "AGENT_ENABLE_VISION", False)
    tool_agent._agent_cache.clear()
    yield
    tool_agent._agent_cache.clear()


def _use_model(monkeypatch, model):
    monkeypatch.setattr(tool_agent, "get_chat_model", lambda **_: SimpleNamespace(langchain_model=model))


def _run(**overrides):
    kwargs = dict(
        db=None,
        current_user=USER,
        message="這筆有幾艘船？",
        history_messages=[],
        mode="auto",
        detection_id=12,
        batch_id=None,
        provider_name="ollama",
        model_name_override="qwen2.5",
    )
    kwargs.update(overrides)
    return list(tool_agent.stream_tool_agent(**kwargs))


# -- engine selection ---------------------------------------------------------

@pytest.mark.parametrize(
    ("engine", "provider", "mode", "vision", "expected"),
    [
        ("tool_calling", "ollama", "auto", False, True),
        ("pipeline", "ollama", "auto", False, False),
        ("tool_calling", "mock", "auto", False, False),
        ("tool_calling", "ollama", "report", False, False),
        ("tool_calling", "ollama", "explain_detection", True, False),
        ("tool_calling", "ollama", "explain_detection", False, True),
    ],
)
def test_engine_selection(monkeypatch, engine, provider, mode, vision, expected):
    monkeypatch.setattr(settings, "AGENT_ENGINE", engine)
    monkeypatch.setattr(settings, "AGENT_ENABLE_VISION", vision)
    assert tool_agent.use_tool_agent(mode=mode, provider_name=provider) is expected


def test_admin_tools_are_only_offered_to_admins():
    names = lambda tools: {t.name for t in tools}  # noqa: E731
    assert not names(tool_agent._tools_for("auto", False)) & {"admin_list_users", "admin_detection_overview"}
    assert {"admin_list_users", "admin_detection_overview"} <= names(tool_agent._tools_for("auto", True))
    assert tool_agent._tools_for("general_chat", False) == []


def test_admin_tool_hard_checks_even_if_called():
    runtime = SimpleNamespace(context=AgentToolContext(db=None, current_user=USER))
    assert langchain_tools.admin_list_users.func(runtime) == {"ok": False, "error": "permission_denied"}


# -- a full run ----------------------------------------------------------------

def test_selected_detection_flows_through_context_not_model(monkeypatch):
    seen = {}

    def fake_detail(db, *, current_user, detection_id):
        seen.update(user=current_user, detection_id=detection_id)
        objects = [
            {"object_index": i, "class_name": "ship", "confidence": 0.9, "bbox": [0, 0, 1, 1]}
            for i in range(60)
        ]
        return {"ok": True, "detection_id": detection_id, "objects": objects, "model_sha256": "x", "model_class_map": {}}

    monkeypatch.setattr(langchain_tools, "get_detection_detail_tool", fake_detail)
    model = ScriptedToolModel(script=[_call("get_detection_detail"), AIMessage(content="YOLO 偵測到 60 艘船。")])
    _use_model(monkeypatch, model)

    events = _run()

    phases = [phase for phase, _ in events]
    assert phases[0] == "ready"
    assert ("tool", {"tool": "get_detection_detail", "status": "running", "args": {}}) in events
    assert ("tool", {"tool": "get_detection_detail", "status": "done", "ok": True}) in events
    assert phases[-1] == "done"
    done = events[-1][1]
    assert done["final_answer"] == "YOLO 偵測到 60 艘船。"
    assert done["tool_results"] == [{"tool": "get_detection_detail", "ok": True}]
    assert done["references"] == [{"type": "detection", "detection_id": 12}]
    # The model never chose the user or the id: both came from runtime context.
    assert seen == {"user": USER, "detection_id": 12}
    assert "admin_list_users" not in model.bound


def test_tool_output_caps_object_list(monkeypatch):
    objects = [{"object_index": i, "class_name": "ship", "confidence": 0.5, "bbox": [0, 0, 2, 2]} for i in range(80)]
    monkeypatch.setattr(
        langchain_tools,
        "get_detection_detail_tool",
        lambda db, **_: {"ok": True, "detection_id": 1, "objects": objects},
    )
    runtime = SimpleNamespace(context=AgentToolContext(db=None, current_user=USER, detection_id=1))
    payload = langchain_tools.get_detection_detail.func(runtime)
    assert len(payload["objects"]) == langchain_tools.MAX_OBJECTS_IN_TOOL_RESULT
    assert payload["objects_truncated"] is True
    assert payload["stats"]["object_count"] == 80


def test_missing_selection_asks_instead_of_guessing():
    runtime = SimpleNamespace(context=AgentToolContext(db=None, current_user=USER))
    assert langchain_tools.get_detection_detail.func(runtime)["error"] == "detection_id_required"


def test_run_tool_agent_collects_result(monkeypatch):
    model = ScriptedToolModel(script=[AIMessage(content="你好！")])
    _use_model(monkeypatch, model)
    result = tool_agent.run_tool_agent(
        db=None, current_user=USER, message="hi", history_messages=[], mode="general_chat",
        detection_id=None, provider_name="ollama", model_name_override="qwen2.5",
    )
    assert result["final_answer"] == "你好！"
    assert result["errors"] == []
    assert model.bound == []


# -- errors match the pipeline engine ------------------------------------------

def test_missing_detection_in_explain_mode_matches_pipeline_message():
    events = _run(mode="explain_detection", detection_id=None)
    assert events[-1] == ("error", "請提供有效的 detection_id 才能解釋 YOLO 結果。")


def test_non_admin_admin_help_is_denied_before_model_runs(monkeypatch):
    monkeypatch.setattr(tool_agent, "get_chat_model", lambda **_: pytest.fail("model must not be built"))
    result = tool_agent.run_tool_agent(
        db=None, current_user=USER, message="list users", history_messages=[], mode="admin_help",
        detection_id=None, provider_name="ollama", model_name_override="qwen2.5",
    )
    assert result["errors"] == ["permission_denied"]


def test_unconfigured_provider_is_explicit(monkeypatch):
    def boom(**_):
        raise tool_agent.AgentLLMConfigurationError("no key")

    monkeypatch.setattr(tool_agent, "get_chat_model", boom)
    result = tool_agent.run_tool_agent(
        db=None, current_user=USER, message="hi", history_messages=[], mode="auto",
        detection_id=None, provider_name="openai", model_name_override="gpt-4.1-mini",
    )
    assert result["errors"] == ["llm_not_configured"]


def test_model_failure_is_reported(monkeypatch):
    class Broken(ScriptedToolModel):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    _use_model(monkeypatch, Broken(script=[]))
    events = _run(mode="general_chat", detection_id=None)
    assert events[-1][0] == "error"


def test_explain_follow_up_gets_selected_record_without_a_tool_call(monkeypatch):
    monkeypatch.setattr(
        langchain_tools,
        "get_detection_detail_tool",
        lambda db, **_: {"ok": True, "detection_id": 12, "objects": [
            {"object_index": 1, "class_name": "airplane", "confidence": 0.38, "bbox": [0, 0, 1, 1]}]},
    )
    model = ScriptedToolModel(script=[AIMessage(content="第二個物件是 airplane，信心 0.38。")])
    _use_model(monkeypatch, model)

    events = _run(
        mode="explain_detection",
        message="那第二個物件呢？",
        history_messages=[{"role": "user", "content": "第一個？"}, {"role": "assistant", "content": "ship"}],
    )

    assert events[-1][0] == "done"
    context_text = model.seen_messages[1].content
    assert "selected detection_id=12" in context_text
    assert '"class_name": "airplane"' in context_text
    assert [type(m).__name__ for m in model.seen_messages] == [
        "SystemMessage", "SystemMessage", "HumanMessage", "AIMessage", "HumanMessage",
    ]
