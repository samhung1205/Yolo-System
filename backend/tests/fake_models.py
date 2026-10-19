"""Shared fake LangChain chat model for tool-calling engine tests."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedToolModel(BaseChatModel):
    """Returns the scripted AIMessages in order; records bound tool names."""

    script: list[Any]
    bound: list[str] = []
    seen_messages: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        self.bound = [getattr(t, "name", str(t)) for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen_messages = list(messages)
        return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])
