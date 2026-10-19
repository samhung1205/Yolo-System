"""
LangGraph supervisor workflow.

```
classify_intent -> call_tools_or_subagent -> compose_answer
                                        \\-> handle_error
```

The graph is compiled once per process. Per-request dependencies (the DB
session and the authenticated user) travel in LangGraph's runtime context, so
nothing request-specific is captured in the compiled graph.

``run_graph`` (``invoke``) and ``stream_graph`` (``stream``) execute the same
compiled graph. ``compose_answer`` always streams the model and pushes each
delta through LangGraph's stream writer: in ``stream`` mode those deltas reach
the caller as ``custom`` events, in ``invoke`` mode the writer is a no-op and
only the final state is returned.

When LangGraph is not installed, the same node functions run as a plain Python
pipeline so the rest of the system stays usable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Optional

from sqlalchemy.orm import Session

from app.agents import subagents
from app.agents.llm import (
    AgentLLMConfigurationError,
    AgentLLMInvocationError,
    deepagents_available,
    langgraph_available,
    get_chat_model,
)
from app.agents.prompts import (
    AGENT_UNAVAILABLE_MESSAGE,
    GENERAL_CHAT_PROMPT,
    PERMISSION_DENIED_MESSAGE,
    SUPERVISOR_INTENT_PROMPT,
)
from app.agents.state import AgentState
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

LLM_NOT_CONFIGURED_MESSAGE = "所選的模型供應商尚未設定完成，請改用其他模型。"
LLM_FAILED_MESSAGE = "AI 模型目前無法完成回覆，請稍後再試或選擇其他模型。"


MODE_TO_INTENT = {
    "general_chat": "general_chat",
    "explain_detection": "explain_detection",
    "history_analysis": "detection_history_analysis",
    "report": "generate_report",
    "admin_help": "admin_help",
    "batch_analysis": "batch_analysis",
}


@dataclass
class AgentRuntimeContext:
    """Per-request dependencies passed to nodes via LangGraph runtime context."""

    db: Session
    current_user: User


def _classify_intent_node(state: AgentState) -> AgentState:
    """Pick an intent based on the explicit mode, then on heuristics."""
    mode = (state.get("mode") or "auto").lower()
    detection_id = state.get("detection_id")
    batch_id = state.get("batch_id")
    message = (state.get("messages") or [{}])[-1].get("content", "") if state.get("messages") else ""

    if mode != "auto" and mode in MODE_TO_INTENT:
        state["intent"] = MODE_TO_INTENT[mode]
        return state

    text = (message or "").lower()
    if batch_id and any(
        keyword in text for keyword in ("batch", "批次", "資料夾", "folder", "整批", "這批")
    ):
        state["intent"] = "batch_analysis"
        return state
    if batch_id and not detection_id:
        state["intent"] = "batch_analysis"
        return state
    if detection_id and any(keyword in text for keyword in ("report", "報告", "リポート")):
        state["intent"] = "generate_report"
        return state
    if detection_id:
        state["intent"] = "explain_detection"
        return state
    if state.get("is_admin") and any(
        keyword in text for keyword in ("admin", "管理", "使用者", "users", "user list")
    ):
        state["intent"] = "admin_help"
        return state
    if any(
        keyword in text
        for keyword in (
            "history",
            "歷史",
            "记录",
            "紀錄",
            "summary",
            "summarise",
            "summarize",
            "統計",
            "统计",
        )
    ):
        state["intent"] = "detection_history_analysis"
        return state

    state["intent"] = "general_chat"
    return state


def _with_history(
    messages: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Insert prior turns after the leading system messages.

    Every mode gets the conversation so follow-ups ("那第二個物件呢？") keep
    their context; the fresh tool data stays in the latest user turn.
    """
    if not history:
        return messages
    split = 0
    while split < len(messages) and messages[split].get("role") == "system":
        split += 1
    return messages[:split] + list(history) + messages[split:]


def _call_tools_or_subagent_node(state: AgentState, runtime) -> AgentState:
    db: Session = runtime.context.db
    current_user: User = runtime.context.current_user
    intent = state.get("intent") or "general_chat"
    references: list[dict[str, Any]] = state.get("references") or []
    tool_results: list[dict[str, Any]] = state.get("tool_results") or []
    history = state.get("history") or []
    user_text = state["messages"][-1]["content"] if state.get("messages") else ""

    def fail(error: str) -> AgentState:
        state["errors"] = (state.get("errors") or []) + [error]
        return state

    def vision_result(payload: dict[str, Any]) -> None:
        image_payload = payload.get("image")
        if isinstance(image_payload, dict):
            tool_results.append(
                {
                    "tool": "vision_image",
                    "ok": bool(image_payload.get("ok")),
                    "detail": image_payload.get("path_used") or image_payload.get("error"),
                }
            )

    try:
        if intent == "explain_detection":
            detection_id = state.get("detection_id")
            if not detection_id:
                return fail("explain_detection requires detection_id")
            payload = subagents.run_yolo_explainer(
                db,
                current_user=current_user,
                detection_id=int(detection_id),
            )
            if not payload.get("ok"):
                return fail(payload.get("error", "explain_detection failed"))
            tool_results.append({"tool": "yolo_explainer", "ok": True})
            vision_result(payload)
            references.append({"type": "detection", "detection_id": int(detection_id)})
            state["llm_messages"] = _with_history(
                subagents.build_yolo_explainer_messages(user_text, payload), history
            )

        elif intent == "detection_history_analysis":
            payload = subagents.run_history_analyst(db, current_user=current_user)
            tool_results.append({"tool": "history_analyst", "ok": payload.get("ok", False)})
            state["llm_messages"] = _with_history(
                subagents.build_history_analyst_messages(user_text, payload), history
            )

        elif intent == "generate_report":
            detection_id = state.get("detection_id")
            if not detection_id:
                return fail("generate_report requires detection_id")
            payload = subagents.run_report_agent(
                db,
                current_user=current_user,
                detection_id=int(detection_id),
            )
            if not payload.get("ok"):
                return fail(payload.get("error", "report generation failed"))
            tool_results.append({"tool": "report_agent", "ok": True})
            vision_result(payload)
            references.append({"type": "detection", "detection_id": int(detection_id)})
            state["llm_messages"] = _with_history(
                subagents.build_report_agent_messages(user_text, payload), history
            )
            state["report_markdown"] = payload.get("markdown")

        elif intent == "batch_analysis":
            batch_id = state.get("batch_id")
            if not batch_id:
                return fail("batch_analysis requires batch_id")
            payload = subagents.run_batch_analyst(
                db,
                current_user=current_user,
                batch_id=int(batch_id),
            )
            if not payload.get("ok"):
                return fail(payload.get("error", "batch_analysis failed"))
            tool_results.append({"tool": "batch_analyst", "ok": True})
            references.append({"type": "batch", "batch_id": int(batch_id)})
            state["llm_messages"] = _with_history(
                subagents.build_batch_analyst_messages(user_text, payload), history
            )

        elif intent == "admin_help":
            if not current_user.is_admin:
                return fail("permission_denied")
            payload = subagents.run_admin_assistant(db, current_user=current_user)
            tool_results.append({"tool": "admin_assistant", "ok": payload.get("ok", False)})
            state["llm_messages"] = _with_history(
                subagents.build_admin_assistant_messages(user_text, payload), history
            )

        else:
            system = [
                {"role": "system", "content": settings.AGENT_SYSTEM_PROMPT},
                {"role": "system", "content": GENERAL_CHAT_PROMPT},
            ]
            state["llm_messages"] = _with_history(
                system + [{"role": "user", "content": user_text}], history
            )
            tool_results.append({"tool": "general_chat", "ok": True})

    except PermissionError as exc:
        state["errors"] = (state.get("errors") or []) + [str(exc)]
    except Exception:  # pragma: no cover - defensive
        logger.exception("subagent dispatch failed")
        state["errors"] = (state.get("errors") or []) + ["internal_error"]

    state["tool_results"] = tool_results
    state["references"] = references
    return state


def _stream_writer() -> Callable[[Any], None]:
    """LangGraph's stream writer, or a no-op outside a running graph."""
    try:
        from langgraph.config import get_stream_writer  # type: ignore import-not-found

        return get_stream_writer()
    except Exception:
        return lambda _chunk: None


def _compose_answer_node(state: AgentState) -> AgentState:
    if state.get("errors"):
        return state

    def finish(answer: str, error: Optional[str] = None) -> AgentState:
        if error:
            state["errors"] = (state.get("errors") or []) + [error]
        state["final_answer"] = answer
        state.pop("llm_messages", None)
        state.pop("report_markdown", None)
        return state

    try:
        llm = get_chat_model(
            provider=state.get("provider_name"),
            model_name=state.get("model_name_override"),
        )
    except AgentLLMConfigurationError as exc:
        logger.warning("Agent LLM not configured: %s", exc)
        return finish(LLM_NOT_CONFIGURED_MESSAGE, "llm_not_configured")

    write = _stream_writer()
    report_markdown = state.get("report_markdown")
    header = f"{report_markdown}\n\n---\n\n" if report_markdown else ""
    if header:
        write({"delta": header})

    parts: list[str] = []
    try:
        for chunk in llm.stream(state.get("llm_messages") or []):
            delta = chunk.content or ""
            if delta:
                parts.append(delta)
                write({"delta": delta})
    except AgentLLMInvocationError as exc:
        logger.warning("Agent LLM failed: %s", exc)
        return finish(LLM_FAILED_MESSAGE, "llm_invocation_failed")

    llm_text = "".join(parts).strip() or "(no answer)"
    return finish(header + llm_text)


def _handle_error_node(state: AgentState) -> AgentState:
    errors = state.get("errors") or []
    if not errors:
        return state

    if "permission_denied" in errors:
        state["final_answer"] = PERMISSION_DENIED_MESSAGE
    elif any(err.startswith("explain_detection requires") for err in errors):
        state["final_answer"] = "請提供有效的 detection_id 才能解釋 YOLO 結果。"
    elif any(err.startswith("generate_report requires") for err in errors):
        state["final_answer"] = "請提供有效的 detection_id 才能產出報告。"
    elif any(err.startswith("batch_analysis requires") for err in errors):
        state["final_answer"] = "請提供有效的 batch_id 才能分析這批影像。"
    elif any("batch_not_found_or_not_owned" in err for err in errors):
        state["final_answer"] = "找不到指定的批次，或您無權存取此批次，請確認 batch_id 是否正確。"
    elif any("not allowed" in err for err in errors):
        state["final_answer"] = "您無權存取指定的偵測任務。"
    elif any("not found" in err for err in errors):
        state["final_answer"] = "找不到指定的偵測任務，請確認 detection_id 是否正確。"
    else:
        # Unknown error strings may carry internal details; they stay in the
        # server log (see the logger calls at the failure sites).
        state["final_answer"] = "Agent 執行失敗，請稍後再試。"

    state.pop("llm_messages", None)
    state.pop("report_markdown", None)
    return state


def _route_after_tools(state: AgentState) -> str:
    return "handle_error" if state.get("errors") else "compose_answer"


def _build_state(
    *,
    user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
    batch_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
) -> AgentState:
    return AgentState(
        messages=history_messages + [{"role": "user", "content": message}],
        history=history_messages,
        conversation_id=conversation_id,
        user_id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin),
        mode=(mode or "auto").lower(),
        intent="",
        detection_id=int(detection_id) if detection_id is not None else None,
        batch_id=int(batch_id) if batch_id is not None else None,
        tool_results=[],
        final_answer="",
        references=[],
        errors=[],
        llm_messages=[],
        report_markdown=None,
        provider_name=provider_name or None,
        model_name_override=model_name_override or None,
    )


def _run_plain_pipeline(state: AgentState, context: AgentRuntimeContext) -> AgentState:
    runtime = SimpleNamespace(context=context)
    state = _classify_intent_node(state)
    state = _call_tools_or_subagent_node(state, runtime)
    if _route_after_tools(state) == "handle_error":
        return _handle_error_node(state)
    return _compose_answer_node(state)


_compiled_graph = None


def _get_compiled_graph():
    """Compile the supervisor graph once; caller must check langgraph_available()."""
    global _compiled_graph
    if _compiled_graph is None:
        from langgraph.graph import END, StateGraph  # type: ignore import-not-found

        workflow = StateGraph(AgentState, context_schema=AgentRuntimeContext)
        workflow.add_node("classify_intent", _classify_intent_node)
        workflow.add_node("call_tools_or_subagent", _call_tools_or_subagent_node)
        workflow.add_node("compose_answer", _compose_answer_node)
        workflow.add_node("handle_error", _handle_error_node)

        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "call_tools_or_subagent")
        workflow.add_conditional_edges(
            "call_tools_or_subagent",
            _route_after_tools,
            {"handle_error": "handle_error", "compose_answer": "compose_answer"},
        )
        workflow.add_edge("compose_answer", END)
        workflow.add_edge("handle_error", END)
        _compiled_graph = workflow.compile()
    return _compiled_graph


def _graph_config() -> dict[str, Any]:
    return {"recursion_limit": max(1, int(settings.AGENT_RECURSION_LIMIT or 25))}


def _result(state: AgentState) -> dict[str, Any]:
    return {
        "intent": state.get("intent"),
        "final_answer": state.get("final_answer") or "",
        "tool_results": state.get("tool_results") or [],
        "references": state.get("references") or [],
        "errors": state.get("errors") or [],
    }


def run_graph(
    *,
    db: Session,
    current_user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
    batch_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
) -> dict[str, Any]:
    """Execute the supervisor workflow and return a serialisable result dict."""
    state = _build_state(
        user=current_user,
        message=message,
        history_messages=history_messages,
        conversation_id=conversation_id,
        mode=mode,
        detection_id=detection_id,
        batch_id=batch_id,
        provider_name=provider_name,
        model_name_override=model_name_override,
    )
    context = AgentRuntimeContext(db=db, current_user=current_user)

    if not langgraph_available():
        logger.info("LangGraph unavailable; using plain Python pipeline")
        return _result(_run_plain_pipeline(state, context))

    final_state = _get_compiled_graph().invoke(state, config=_graph_config(), context=context)
    return _result(final_state)


def stream_graph(
    *,
    db: Session,
    current_user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
    batch_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
) -> Iterator[tuple[str, Any]]:
    """Streaming variant of :func:`run_graph` over the same compiled graph.

    Yields ``(phase, data)`` tuples so the service layer can convert them to
    SSE events without having to know about the graph internals:

    - ``("ready", {"tool_results": [...], "references": [...]})``:
      tool calls completed; LLM streaming is about to begin.
    - ``("answer_chunk", "<text>")``: incremental LLM output.
    - ``("done", {"final_answer": "...", "tool_results": [...], "references": [...]})``
    - ``("error", "<message>")``: the turn failed; caller should stop reading.
    """
    state = _build_state(
        user=current_user,
        message=message,
        history_messages=history_messages,
        conversation_id=conversation_id,
        mode=mode,
        detection_id=detection_id,
        batch_id=batch_id,
        provider_name=provider_name,
        model_name_override=model_name_override,
    )
    context = AgentRuntimeContext(db=db, current_user=current_user)

    if not langgraph_available():
        final_state = _run_plain_pipeline(state, context)
        yield ("ready", {"tool_results": final_state.get("tool_results") or [], "references": final_state.get("references") or []})
        if final_state.get("errors"):
            yield ("error", final_state.get("final_answer") or "Agent 執行失敗。")
            return
        yield ("answer_chunk", final_state.get("final_answer") or "")
        yield ("done", _result(final_state))
        return

    final_state: dict[str, Any] = dict(state)
    for mode_name, payload in _get_compiled_graph().stream(
        state,
        config=_graph_config(),
        context=context,
        stream_mode=["updates", "custom"],
    ):
        if mode_name == "custom":
            delta = payload.get("delta") if isinstance(payload, dict) else None
            if delta:
                yield ("answer_chunk", delta)
            continue

        for node_name, update in (payload or {}).items():
            if update:
                final_state.update(update)
            if node_name == "call_tools_or_subagent":
                yield (
                    "ready",
                    {
                        "tool_results": final_state.get("tool_results") or [],
                        "references": final_state.get("references") or [],
                    },
                )

    if final_state.get("errors"):
        yield ("error", final_state.get("final_answer") or "Agent 執行失敗。")
        return
    yield ("done", _result(final_state))


def describe_runtime() -> dict[str, Any]:
    """Used by the route layer to surface health diagnostics if needed."""
    try:
        llm = get_chat_model()
        provider, model_name = llm.provider, getattr(llm, "model_name", "")
    except AgentLLMConfigurationError:
        provider, model_name = settings.agent_effective_provider, settings.agent_effective_model
    return {
        "langgraph_available": langgraph_available(),
        "deepagents_enabled_and_available": deepagents_available(),
        "llm_provider": provider,
        "llm_model_name": model_name,
        "is_mock": provider == "mock",
        "agent_unavailable_message": AGENT_UNAVAILABLE_MESSAGE,
        "supervisor_intent_prompt_excerpt": SUPERVISOR_INTENT_PROMPT.splitlines()[0],
    }
