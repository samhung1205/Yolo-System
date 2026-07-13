"""
LangGraph state container for the supervisor workflow.

The state intentionally avoids importing ``langchain`` / ``langgraph`` so the
type definitions remain usable even when the agentic dependencies are not
installed.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentMessage(TypedDict, total=False):
    """A lightweight message envelope used inside the graph state."""

    role: str
    content: str


class AgentState(TypedDict, total=False):
    """Mutable state shared across LangGraph nodes."""

    # Conversation context
    messages: list[AgentMessage]
    conversation_id: str
    history: list[AgentMessage]

    # Identity / permissions
    user_id: int
    username: str
    is_admin: bool

    # Routing
    mode: str
    intent: str
    detection_id: Optional[int]

    # Workflow output
    tool_results: list[dict[str, Any]]
    final_answer: str
    references: list[dict[str, Any]]
    errors: list[str]

    # Intermediate values must be declared so LangGraph preserves them between
    # nodes. Undeclared keys are discarded when state transitions are applied.
    llm_messages: list[AgentMessage]
    report_markdown: Optional[str]

    # Per-request LLM override (set by service layer, read by compose_answer_node)
    provider_name: Optional[str]
    model_name_override: Optional[str]
