"""
Tool-calling agent engine (``AGENT_ENGINE=tool_calling``, Agent 重構 B).

Built on LangChain v1 ``create_agent``: the model decides which read-only
tools to call (``app/agents/langchain_tools.py``). Each UI mode exposes a
subset of tools plus mode-specific guidance; ``auto`` exposes all of them.

The pipeline engine in ``graph.py`` stays as the default and as the fallback:
- explicit ``mock`` provider (no tool calling),
- ``report`` mode (its deterministic markdown must not be rewritten),
- ``explain_detection`` with ``AGENT_ENABLE_VISION`` (only the pipeline
  attaches the annotated image).

Both engines yield the same ``(phase, data)`` tuples, so the SSE contract is
unchanged; this engine additionally yields ``("tool", {...})`` progress events.
LangChain is imported lazily so a missing package never breaks API startup.
"""
from __future__ import annotations

import json
import logging
import threading
from types import SimpleNamespace
from typing import Any, Iterator, Optional

from sqlalchemy.orm import Session

from app.agents import graph
from app.agents.llm import AgentLLMConfigurationError, get_chat_model, langchain_available
from app.agents.prompts import TOOL_AGENT_MODE_GUIDANCE, TOOL_AGENT_PROMPT
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

PIPELINE_ONLY_MODES = frozenset({"report"})
_AGENT_CACHE_MAX = 32

_agent_cache: dict[tuple, Any] = {}
_agent_cache_lock = threading.Lock()


def use_tool_agent(*, mode: Optional[str], provider_name: Optional[str]) -> bool:
    """Whether this request should run on the tool-calling engine."""
    if (settings.AGENT_ENGINE or "").strip().lower() != "tool_calling":
        return False
    if not langchain_available():
        return False
    provider = (provider_name or settings.agent_effective_provider or "").strip().lower()
    if provider == "mock":
        return False
    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode in PIPELINE_ONLY_MODES:
        return False
    if settings.AGENT_ENABLE_VISION and normalized_mode == "explain_detection":
        return False
    return True


def _tools_for(mode: str, is_admin: bool) -> list:
    from app.agents import langchain_tools as lt

    by_mode = {
        "general_chat": [],
        "explain_detection": lt.DETECTION_TOOLS,
        "history_analysis": lt.HISTORY_TOOLS + [lt.get_detection_detail],
        "batch_analysis": lt.BATCH_TOOLS,
        "admin_help": lt.ADMIN_TOOLS + [lt.summarize_detection_history],
    }
    if mode in by_mode:
        return list(by_mode[mode])
    # auto: everything the caller is allowed to use. Admin tools also check
    # is_admin themselves, so this filter is only the first line of defence.
    return list(lt.USER_TOOLS) + (list(lt.ADMIN_TOOLS) if is_admin else [])


def _system_prompt(mode: str) -> str:
    guidance = TOOL_AGENT_MODE_GUIDANCE.get(mode, TOOL_AGENT_MODE_GUIDANCE["auto"])
    return "\n\n".join([settings.AGENT_SYSTEM_PROMPT, TOOL_AGENT_PROMPT, f"CURRENT MODE ({mode}): {guidance}"])


def _get_agent(provider: str, model_name: str, mode: str, is_admin: bool):
    """Build (once) the compiled agent for this provider/model/mode/role."""
    key = (provider, model_name, mode, is_admin)
    with _agent_cache_lock:
        cached = _agent_cache.get(key)
    if cached is not None:
        return cached

    from langchain.agents import create_agent  # type: ignore import-not-found
    from langchain.agents.middleware import (  # type: ignore import-not-found
        ModelCallLimitMiddleware,
        ToolCallLimitMiddleware,
    )

    from app.agents.langchain_tools import AgentToolContext

    wrapper = get_chat_model(provider=provider, model_name=model_name)
    lc_model = getattr(wrapper, "langchain_model", None)
    if lc_model is None:
        raise AgentLLMConfigurationError(f"{provider} does not provide a tool-calling chat model")

    tool_limit = max(1, int(settings.AGENT_MAX_TOOL_CALLS or 8))
    agent = create_agent(
        model=lc_model,
        tools=_tools_for(mode, is_admin),
        system_prompt=_system_prompt(mode),
        context_schema=AgentToolContext,
        middleware=[
            # Over the limit, tool calls get an error result and the model
            # must answer with what it has; model calls end the run.
            ToolCallLimitMiddleware(run_limit=tool_limit),
            ModelCallLimitMiddleware(run_limit=tool_limit + 2, exit_behavior="end"),
        ],
    )
    with _agent_cache_lock:
        if len(_agent_cache) >= _AGENT_CACHE_MAX:
            _agent_cache.clear()
        _agent_cache[key] = agent
    return agent


def _precheck(mode: str, detection_id: Optional[int], batch_id: Optional[int], is_admin: bool) -> Optional[str]:
    """Same up-front requirements as the pipeline engine, same messages."""
    if mode == "explain_detection" and not detection_id:
        return "explain_detection requires detection_id"
    if mode == "batch_analysis" and not batch_id:
        return "batch_analysis requires batch_id"
    if mode == "admin_help" and not is_admin:
        return "permission_denied"
    return None


def _context_message(detection_id: Optional[int], batch_id: Optional[int]) -> str:
    parts = []
    if detection_id:
        parts.append(f"selected detection_id={detection_id} (「這筆」「這張」refers to it)")
    if batch_id:
        parts.append(f"selected batch_id={batch_id} (「這批」refers to it)")
    if not parts:
        return "Context: no detection or batch is selected in the UI."
    return "Context: " + "; ".join(parts) + ". Tools use these when you omit the ID argument."


def _prefetched_data(mode: str, context) -> Optional[str]:
    """Selected record's data for the modes that are about one record.

    Stored history keeps only past questions and answers, not tool results,
    so on a follow-up ("那第二個物件呢？") a small model would otherwise answer
    from memory instead of data. Loading the selected record up front gives it
    the same grounding as the pipeline engine; tools stay available for
    anything else.
    """
    from app.agents import langchain_tools as lt

    runtime = SimpleNamespace(context=context)
    if mode == "explain_detection" and context.detection_id:
        tool_name, payload = "get_detection_detail", lt.get_detection_detail.func(runtime)
    elif mode == "batch_analysis" and context.batch_id:
        tool_name, payload = "summarize_batch", lt.summarize_batch.func(runtime)
    else:
        return None
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"Current data from {tool_name} (already loaded; answer from it):\n{data}"


def _message_text(message: Any) -> str:
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else ""


def _tool_result_ok(tool_message: Any) -> bool:
    if getattr(tool_message, "status", "success") == "error":
        return False
    try:
        payload = json.loads(_message_text(tool_message))
    except (TypeError, ValueError):
        return True
    return bool(payload.get("ok", True)) if isinstance(payload, dict) else True


def _add_references(references: list[dict[str, Any]], tool_name: str, args: dict[str, Any], context) -> None:
    def add(ref: dict[str, Any]) -> None:
        if ref not in references:
            references.append(ref)

    for key in ("detection_id", "detection_id_a", "detection_id_b"):
        if args.get(key):
            add({"type": "detection", "detection_id": int(args[key])})
    if args.get("batch_id"):
        add({"type": "batch", "batch_id": int(args["batch_id"])})
    if tool_name in ("get_detection_detail", "generate_detection_report") and not args.get("detection_id") and context.detection_id:
        add({"type": "detection", "detection_id": int(context.detection_id)})
    if tool_name in ("summarize_batch", "list_batch_images_by_class") and not args.get("batch_id") and context.batch_id:
        add({"type": "batch", "batch_id": int(context.batch_id)})


def stream_tool_agent(
    *,
    db: Session,
    current_user: User,
    message: str,
    history_messages: list[dict[str, str]],
    mode: str,
    detection_id: Optional[int],
    batch_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    model_name_override: Optional[str] = None,
    **_unused: Any,
) -> Iterator[tuple[str, Any]]:
    """Run one turn; yields the same phases as ``graph.stream_graph`` plus
    ``tool`` (progress) and ``error_code`` (sent right before ``error``)."""
    from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage  # type: ignore import-not-found

    from app.agents.langchain_tools import AgentToolContext

    normalized_mode = (mode or "auto").strip().lower()
    provider = (provider_name or settings.agent_effective_provider).strip().lower()
    model_name = model_name_override or settings.agent_effective_model
    is_admin = bool(current_user.is_admin)

    error = _precheck(normalized_mode, detection_id, batch_id, is_admin)
    if error:
        yield ("ready", {"tool_results": [], "references": []})
        yield ("error_code", error)
        yield ("error", graph._handle_error_node({"errors": [error]})["final_answer"])
        return

    try:
        agent = _get_agent(provider, model_name, normalized_mode, is_admin)
    except AgentLLMConfigurationError as exc:
        logger.warning("Tool agent LLM not configured: %s", exc)
        yield ("ready", {"tool_results": [], "references": []})
        yield ("error_code", "llm_not_configured")
        yield ("error", graph.LLM_NOT_CONFIGURED_MESSAGE)
        return

    yield ("ready", {"tool_results": [], "references": []})

    context = AgentToolContext(db=db, current_user=current_user, detection_id=detection_id, batch_id=batch_id)
    context_text = _context_message(detection_id, batch_id)
    prefetched = _prefetched_data(normalized_mode, context)
    if prefetched:
        context_text = f"{context_text}\n\n{prefetched}"
    agent_input = {
        "messages": [{"role": "system", "content": context_text}]
        + list(history_messages)
        + [{"role": "user", "content": message}]
    }
    tool_results: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    streamed: list[str] = []
    final_text = ""

    try:
        for stream_mode, payload in agent.stream(
            agent_input,
            context=context,
            config={"recursion_limit": max(5, int(settings.AGENT_RECURSION_LIMIT or 25))},
            stream_mode=["updates", "messages"],
        ):
            if stream_mode == "messages":
                chunk, metadata = payload
                if metadata.get("langgraph_node") == "model" and isinstance(chunk, AIMessageChunk):
                    delta = _message_text(chunk)
                    if delta:
                        streamed.append(delta)
                        yield ("answer_chunk", delta)
                continue

            for node_name, update in (payload or {}).items():
                messages = update.get("messages") if isinstance(update, dict) else None
                for item in messages or []:
                    if isinstance(item, AIMessage) and item.tool_calls:
                        for call in item.tool_calls:
                            args = call.get("args") or {}
                            _add_references(references, call["name"], args, context)
                            yield ("tool", {"tool": call["name"], "status": "running", "args": args})
                    elif isinstance(item, AIMessage):
                        final_text = _message_text(item)
                    elif isinstance(item, ToolMessage):
                        ok = _tool_result_ok(item)
                        tool_results.append({"tool": item.name, "ok": ok})
                        yield ("tool", {"tool": item.name, "status": "done", "ok": ok})
    except Exception:
        logger.exception("Tool agent run failed")
        yield ("error_code", "llm_invocation_failed")
        yield ("error", graph.LLM_FAILED_MESSAGE)
        return

    answer = (final_text or "".join(streamed)).strip() or "(no answer)"
    yield (
        "done",
        {
            "intent": normalized_mode,
            "final_answer": answer,
            "tool_results": tool_results,
            "references": references,
            "errors": [],
        },
    )


def run_tool_agent(**kwargs: Any) -> dict[str, Any]:
    """Non-streaming wrapper: same run, collected into ``graph.run_graph``'s shape."""
    result: dict[str, Any] = {"intent": kwargs.get("mode"), "final_answer": "", "tool_results": [], "references": [], "errors": []}
    tool_results: list[dict[str, Any]] = []
    for phase, data in stream_tool_agent(**kwargs):
        if phase == "done":
            result.update(data)
        elif phase == "tool" and data.get("status") == "done":
            tool_results.append({"tool": data["tool"], "ok": data.get("ok", True)})
        elif phase == "error_code":
            result["errors"] = [data]
        elif phase == "error":
            result["final_answer"] = data
            result["tool_results"] = tool_results
    return result
