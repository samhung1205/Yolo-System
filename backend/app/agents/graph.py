"""
LangGraph supervisor workflow.

Phase 6A-1 keeps the graph deliberately small:

```
classify_intent -> call_tools_or_subagent -> compose_answer
                                        \-> handle_error
```

When LangGraph is unavailable, :func:`run_graph` falls back to the same logic
executed as a plain Python pipeline so the rest of the system stays usable
(useful for unit tests, mock providers, or CI without optional dependencies).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.agents import subagents
from app.agents.llm import (
    MockChatModel,
    deepagents_available,
    get_chat_model,
    langgraph_available,
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


MODE_TO_INTENT = {
    "general_chat": "general_chat",
    "explain_detection": "explain_detection",
    "history_analysis": "detection_history_analysis",
    "report": "generate_report",
    "admin_help": "admin_help",
}


def _classify_intent_node(state: AgentState) -> AgentState:
    """Pick an intent based on the explicit mode, then on heuristics."""
    mode = (state.get("mode") or "auto").lower()
    detection_id = state.get("detection_id")
    message = (state.get("messages") or [{}])[-1].get("content", "") if state.get("messages") else ""

    if mode != "auto" and mode in MODE_TO_INTENT:
        state["intent"] = MODE_TO_INTENT[mode]
        return state

    text = (message or "").lower()
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


def _tool_results_to_messages(
    state: AgentState,
    payload: dict[str, Any] | None,
    builder: Callable[[str, dict[str, Any]], list[dict[str, str]]],
) -> list[dict[str, str]]:
    last_message = (state.get("messages") or [{}])[-1].get("content", "") if state.get("messages") else ""
    return builder(last_message, payload or {})


def _call_tools_or_subagent_node(state: AgentState, *, db: Session, current_user: User) -> AgentState:
    intent = state.get("intent") or "general_chat"
    references: list[dict[str, Any]] = state.get("references") or []
    tool_results: list[dict[str, Any]] = state.get("tool_results") or []

    try:
        if intent == "explain_detection":
            detection_id = state.get("detection_id")
            if not detection_id:
                state["errors"] = (state.get("errors") or []) + [
                    "explain_detection requires detection_id"
                ]
                return state
            payload = subagents.run_yolo_explainer(
                db,
                current_user=current_user,
                detection_id=int(detection_id),
            )
            if not payload.get("ok"):
                state["errors"] = (state.get("errors") or []) + [
                    payload.get("error", "explain_detection failed")
                ]
                return state
            tool_results.append({"tool": "yolo_explainer", "ok": True})
            references.append({"type": "detection", "detection_id": int(detection_id)})
            state["__llm_messages"] = subagents.build_yolo_explainer_messages(
                state["messages"][-1]["content"] if state.get("messages") else "",
                payload,
            )

        elif intent == "detection_history_analysis":
            payload = subagents.run_history_analyst(db, current_user=current_user)
            tool_results.append({"tool": "history_analyst", "ok": payload.get("ok", False)})
            state["__llm_messages"] = subagents.build_history_analyst_messages(
                state["messages"][-1]["content"] if state.get("messages") else "",
                payload,
            )

        elif intent == "generate_report":
            detection_id = state.get("detection_id")
            if not detection_id:
                state["errors"] = (state.get("errors") or []) + [
                    "generate_report requires detection_id"
                ]
                return state
            payload = subagents.run_report_agent(
                db,
                current_user=current_user,
                detection_id=int(detection_id),
            )
            if not payload.get("ok"):
                state["errors"] = (state.get("errors") or []) + [
                    payload.get("error", "report generation failed")
                ]
                return state
            tool_results.append({"tool": "report_agent", "ok": True})
            references.append({"type": "detection", "detection_id": int(detection_id)})
            state["__llm_messages"] = subagents.build_report_agent_messages(
                state["messages"][-1]["content"] if state.get("messages") else "",
                payload,
            )
            state["__report_markdown"] = payload.get("markdown")

        elif intent == "admin_help":
            if not current_user.is_admin:
                state["errors"] = (state.get("errors") or []) + ["permission_denied"]
                return state
            payload = subagents.run_admin_assistant(db, current_user=current_user)
            tool_results.append({"tool": "admin_assistant", "ok": payload.get("ok", False)})
            state["__llm_messages"] = subagents.build_admin_assistant_messages(
                state["messages"][-1]["content"] if state.get("messages") else "",
                payload,
            )

        else:
            history = state.get("history") or []
            system = [{"role": "system", "content": settings.AGENT_SYSTEM_PROMPT}]
            extra = [{"role": "system", "content": GENERAL_CHAT_PROMPT}]
            user_msg = state["messages"][-1] if state.get("messages") else {
                "role": "user",
                "content": "",
            }
            state["__llm_messages"] = system + extra + history + [user_msg]
            tool_results.append({"tool": "general_chat", "ok": True})

    except PermissionError as exc:
        state["errors"] = (state.get("errors") or []) + [str(exc)]
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("subagent dispatch failed")
        state["errors"] = (state.get("errors") or []) + [f"unexpected error: {exc}"]

    state["tool_results"] = tool_results
    state["references"] = references
    return state


def _compose_answer_node(state: AgentState) -> AgentState:
    if state.get("errors"):
        return state

    messages = state.get("__llm_messages") or []
    llm = get_chat_model(
        provider=state.get("provider_name"),
        model_name=state.get("model_name_override"),
    )
    response = llm.invoke(messages)
    answer = (response.content or "").strip() or "(no answer)"

    report_markdown = state.get("__report_markdown")
    if report_markdown:
        answer = f"{report_markdown}\n\n---\n\n{answer}"

    state["final_answer"] = answer
    state.pop("__llm_messages", None)
    state.pop("__report_markdown", None)
    return state


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
    elif any("not allowed" in err for err in errors):
        state["final_answer"] = "您無權存取指定的偵測任務。"
    elif any("not found" in err for err in errors):
        state["final_answer"] = "找不到指定的偵測任務，請確認 detection_id 是否正確。"
    else:
        state["final_answer"] = f"Agent 執行失敗：{errors[0]}"

    state.pop("__llm_messages", None)
    state.pop("__report_markdown", None)
    return state


def _build_state(
    *,
    user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
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
        tool_results=[],
        final_answer="",
        references=[],
        errors=[],
        provider_name=provider_name or None,
        model_name_override=model_name_override or None,
    )


def _run_plain_pipeline(state: AgentState, *, db: Session, current_user: User) -> AgentState:
    state = _classify_intent_node(state)
    state = _call_tools_or_subagent_node(state, db=db, current_user=current_user)
    if state.get("errors"):
        return _handle_error_node(state)
    return _compose_answer_node(state)


def _build_langgraph_app(db: Session, current_user: User):
    """Compile a LangGraph state graph. Caller must have verified availability."""
    from langgraph.graph import END, StateGraph  # type: ignore import-not-found

    def classify(state: AgentState) -> AgentState:
        return _classify_intent_node(state)

    def tools(state: AgentState) -> AgentState:
        return _call_tools_or_subagent_node(state, db=db, current_user=current_user)

    def compose(state: AgentState) -> AgentState:
        return _compose_answer_node(state)

    def handle_error(state: AgentState) -> AgentState:
        return _handle_error_node(state)

    def has_error(state: AgentState) -> str:
        return "handle_error" if state.get("errors") else "compose_answer"

    workflow = StateGraph(AgentState)
    workflow.add_node("classify_intent", classify)
    workflow.add_node("call_tools_or_subagent", tools)
    workflow.add_node("compose_answer", compose)
    workflow.add_node("handle_error", handle_error)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "call_tools_or_subagent")
    workflow.add_conditional_edges(
        "call_tools_or_subagent",
        has_error,
        {"handle_error": "handle_error", "compose_answer": "compose_answer"},
    )
    workflow.add_edge("compose_answer", END)
    workflow.add_edge("handle_error", END)
    return workflow.compile()


def run_graph(
    *,
    db: Session,
    current_user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
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
        provider_name=provider_name,
        model_name_override=model_name_override,
    )

    if not langgraph_available():
        logger.info("LangGraph unavailable; using plain Python pipeline")
        state = _run_plain_pipeline(state, db=db, current_user=current_user)
    else:
        try:
            compiled = _build_langgraph_app(db, current_user)
            recursion_limit = max(1, int(settings.AGENT_RECURSION_LIMIT or 25))
            state = compiled.invoke(state, {"recursion_limit": recursion_limit})
        except Exception as exc:
            logger.warning("LangGraph execution failed (%s); falling back to plain pipeline", exc)
            state = _run_plain_pipeline(state, db=db, current_user=current_user)

    return {
        "intent": state.get("intent"),
        "final_answer": state.get("final_answer") or "",
        "tool_results": state.get("tool_results") or [],
        "references": state.get("references") or [],
        "errors": state.get("errors") or [],
    }


def stream_graph(
    *,
    db: Session,
    current_user: User,
    message: str,
    history_messages: list[dict[str, str]],
    conversation_id: str,
    mode: str,
    detection_id: Optional[int],
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
):
    """Streaming variant of :func:`run_graph`.

    Yields ``(phase, data)`` tuples so the service layer can convert them to
    SSE events without having to know about the graph internals:

    - ``("ready", {"tool_results": [...], "references": [...]})``:
      tool calls completed; LLM streaming is about to begin.
    - ``("answer_chunk", "<text>")``:
      incremental LLM output.
    - ``("done", {"final_answer": "...", "tool_results": [...], "references": [...]})``:
      streaming finished.
    - ``("error", "<message>")``:
      unrecoverable error; caller should stop reading.
    """
    state = _build_state(
        user=current_user,
        message=message,
        history_messages=history_messages,
        conversation_id=conversation_id,
        mode=mode,
        detection_id=detection_id,
        provider_name=provider_name,
        model_name_override=model_name_override,
    )

    state = _classify_intent_node(state)
    state = _call_tools_or_subagent_node(state, db=db, current_user=current_user)

    tool_results: list[dict[str, Any]] = state.get("tool_results") or []
    references: list[dict[str, Any]] = state.get("references") or []
    report_markdown: Optional[str] = state.get("__report_markdown")

    yield ("ready", {"tool_results": tool_results, "references": references})

    if state.get("errors"):
        state = _handle_error_node(state)
        answer = state.get("final_answer") or ""
        if answer:
            yield ("answer_chunk", answer)
        yield ("done", {"final_answer": answer, "tool_results": tool_results, "references": references})
        return

    if report_markdown:
        header = report_markdown + "\n\n---\n\n"
        yield ("answer_chunk", header)

    messages_for_llm = state.get("__llm_messages") or []
    llm = get_chat_model(
        provider=state.get("provider_name"),
        model_name=state.get("model_name_override"),
    )
    full_parts: list[str] = [report_markdown + "\n\n---\n\n"] if report_markdown else []

    try:
        for chunk_resp in llm.stream(messages_for_llm):
            delta = chunk_resp.content or ""
            if delta:
                full_parts.append(delta)
                yield ("answer_chunk", delta)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("LLM streaming failed in stream_graph")
        yield ("error", f"LLM streaming failed: {exc}")
        return

    final_answer = "".join(full_parts).strip()
    yield ("done", {"final_answer": final_answer, "tool_results": tool_results, "references": references})


def describe_runtime() -> dict[str, Any]:
    """Used by the route layer to surface health diagnostics if needed."""
    llm = get_chat_model()
    return {
        "langgraph_available": langgraph_available(),
        "deepagents_enabled_and_available": deepagents_available(),
        "llm_provider": llm.provider,
        "llm_model_name": getattr(llm, "model_name", ""),
        "is_mock": isinstance(llm, MockChatModel),
        "agent_unavailable_message": AGENT_UNAVAILABLE_MESSAGE,
        "supervisor_intent_prompt_excerpt": SUPERVISOR_INTENT_PROMPT.splitlines()[0],
    }
