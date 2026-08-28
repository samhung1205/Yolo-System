"""
LLM factory for the agentic layer.

This module returns an object exposing a minimal ``invoke(messages)`` API so
the rest of the agent layer can stay decoupled from LangChain / LangGraph
specifics. When LangChain (or an API key) is unavailable it transparently
returns a :class:`MockChatModel` so the graph can still produce useful
deterministic responses for local validation, CI, or smoke testing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentLLMResponse:
    """Provider-agnostic response wrapper."""

    content: str
    provider: str
    model_name: str


class AgentLLMInvocationError(RuntimeError):
    """Raised when a configured real LLM cannot complete a request."""


class _BaseAgentChatModel:
    provider: str = "base"
    model_name: str = ""

    def invoke(self, messages: list[dict[str, str]]) -> AgentLLMResponse:
        raise NotImplementedError

    def stream(self, messages: list[dict[str, str]]) -> Iterable[AgentLLMResponse]:
        """Yield response chunks.  Default: emit the full invoke result as one chunk."""
        yield self.invoke(messages)


def _mock_text_content(content: Any) -> str:
    """Extract the text portion of a message content (str or multimodal list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(part for part in parts if part)
    return ""


def _content_has_image(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    return any(
        isinstance(block, dict) and block.get("type") == "image_url" for block in content
    )


class MockChatModel(_BaseAgentChatModel):
    """Deterministic mock used when no real provider can be configured.

    The mock simply echoes the latest user message and quotes any pre-computed
    tool output found in the conversation so the surrounding graph remains
    useful for local verification.
    """

    provider = "mock"

    def __init__(self, model_name: str = "mock-agent") -> None:
        self.model_name = model_name

    def invoke(self, messages: list[dict[str, str]]) -> AgentLLMResponse:
        user_message = ""
        tool_payload = ""
        has_image = False
        for entry in reversed(messages):
            if not isinstance(entry, dict):
                continue
            role = (entry.get("role") or "").lower()
            raw_content = entry.get("content")
            content = _mock_text_content(raw_content)
            if _content_has_image(raw_content):
                has_image = True
            if role == "tool" and not tool_payload:
                tool_payload = content
            elif role == "user" and not user_message:
                user_message = content
            if user_message and tool_payload:
                break

        sections: list[str] = ["[mock-agent] 我已收到您的請求。"]
        if has_image:
            sections.append("（此模式已附上偵測影像，但 mock provider 不會實際讀取圖片內容。）")
        if user_message:
            sections.append(f"使用者訊息：{user_message.strip()[:300]}")
        if tool_payload:
            sections.append("以下是工具回傳的摘要：")
            sections.append(tool_payload.strip()[:1500])
        sections.append(
            "提示：未設定 OPENAI_API_KEY 或 langchain 未安裝時，agent 會回傳此 mock 內容。"
        )
        return AgentLLMResponse(
            content="\n".join(sections),
            provider=self.provider,
            model_name=self.model_name,
        )

    def stream(self, messages: list[dict[str, str]]) -> Iterable[AgentLLMResponse]:
        """Simulate streaming by yielding the mock response word-by-word."""
        result = self.invoke(messages)
        words = result.content.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            yield AgentLLMResponse(
                content=chunk,
                provider=self.provider,
                model_name=self.model_name,
            )


class _LangChainChatModel(_BaseAgentChatModel):
    """Thin wrapper around a langchain-openai ``ChatOpenAI`` instance."""

    def __init__(self, langchain_model: Any, provider: str, model_name: str) -> None:
        self._model = langchain_model
        self.provider = provider
        self.model_name = model_name

    def invoke(self, messages: list[dict[str, str]]) -> AgentLLMResponse:
        if not messages:
            raise AgentLLMInvocationError("Agent message payload is empty.")
        try:
            lc_messages = _to_langchain_messages(messages)
            if not lc_messages:
                raise AgentLLMInvocationError("Agent message payload is empty.")
            response = self._model.invoke(lc_messages)
        except AgentLLMInvocationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("LangChain chat model invocation failed: %s", exc)
            raise AgentLLMInvocationError(
                f"{self.provider}/{self.model_name} invocation failed"
            ) from exc

        content = getattr(response, "content", None)
        if isinstance(content, list):
            parts: list[str] = []
            for chunk in content:
                if isinstance(chunk, dict) and isinstance(chunk.get("text"), str):
                    parts.append(chunk["text"])
                elif isinstance(chunk, str):
                    parts.append(chunk)
            content = "".join(parts)
        if not isinstance(content, str):
            content = str(content or "")
        return AgentLLMResponse(
            content=content.strip(),
            provider=self.provider,
            model_name=self.model_name,
        )

    def stream(self, messages: list[dict[str, str]]) -> Iterable[AgentLLMResponse]:
        """Delegate to LangChain's native streaming interface."""
        if not messages:
            raise AgentLLMInvocationError("Agent message payload is empty.")
        try:
            lc_messages = _to_langchain_messages(messages)
            if not lc_messages:
                raise AgentLLMInvocationError("Agent message payload is empty.")
            for lc_chunk in self._model.stream(lc_messages):
                delta = getattr(lc_chunk, "content", "") or ""
                if isinstance(delta, list):
                    delta = "".join(
                        (c["text"] if isinstance(c, dict) else str(c)) for c in delta
                    )
                if not isinstance(delta, str):
                    delta = str(delta)
                if delta:
                    yield AgentLLMResponse(
                        content=delta,
                        provider=self.provider,
                        model_name=self.model_name,
                    )
        except AgentLLMInvocationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("LangChain streaming failed: %s; falling back to invoke", exc)
            yield self.invoke(messages)


def _to_langchain_messages(messages: Iterable[dict[str, str]]) -> list[Any]:
    """Convert plain dict messages to LangChain message objects."""
    from langchain_core.messages import (  # type: ignore import-not-found
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    converted: list[Any] = []
    for entry in messages:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "user").lower()
        content = entry.get("content") or ""
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        elif role == "tool":
            converted.append(
                ToolMessage(content=content, tool_call_id=entry.get("tool_call_id") or "tool")
            )
        else:
            converted.append(HumanMessage(content=content))
    return converted


def _build_ollama_model(model_name: str) -> _BaseAgentChatModel:
    """Build an Ollama LLM wrapper using its OpenAI-compatible endpoint.

    Two strategies are tried in order:
    1. ``langchain-ollama`` (``ChatOllama``) — if the optional package is installed.
    2. ``langchain-openai`` (``ChatOpenAI``) pointed at Ollama's ``/v1`` endpoint —
       uses what is already in requirements.txt.

    No API key is required; Ollama runs locally.
    """
    base_url = (settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
    effective_model = model_name or settings.OLLAMA_MODEL or "llama3.2"

    # Strategy 1: dedicated langchain-ollama package
    try:
        from langchain_ollama import ChatOllama  # type: ignore import-not-found

        lc_model = ChatOllama(
            base_url=base_url,
            model=effective_model,
            timeout=max(settings.CHAT_REQUEST_TIMEOUT, 120),
        )
        logger.info("Ollama agent LLM using langchain-ollama.ChatOllama (%s)", effective_model)
        return _LangChainChatModel(lc_model, provider="ollama", model_name=effective_model)
    except ImportError:
        pass  # fall through to strategy 2

    # Strategy 2: langchain-openai pointed at Ollama's OpenAI-compatible /v1 endpoint
    try:
        from langchain_openai import ChatOpenAI  # type: ignore import-not-found

        lc_model = ChatOpenAI(
            api_key="ollama",  # Ollama ignores the key; a non-empty string is required
            base_url=f"{base_url}/v1",
            model=effective_model,
            timeout=max(settings.CHAT_REQUEST_TIMEOUT, 120),
        )
        logger.info(
            "Ollama agent LLM using langchain-openai.ChatOpenAI → %s/v1 (%s)",
            base_url,
            effective_model,
        )
        return _LangChainChatModel(lc_model, provider="ollama", model_name=effective_model)
    except ImportError:
        pass  # fall through to mock

    logger.warning(
        "Neither langchain-ollama nor langchain-openai is installed; "
        "Ollama agent falling back to mock. Run: pip install langchain-openai"
    )
    return MockChatModel(model_name=effective_model)


def get_chat_model(provider: Optional[str] = None, model_name: Optional[str] = None) -> _BaseAgentChatModel:
    """Return an LLM wrapper, falling back to :class:`MockChatModel` on error."""
    effective_provider = (provider or settings.agent_effective_provider or "mock").lower()
    effective_model = model_name or settings.agent_effective_model or "mock-agent"

    if effective_provider == "mock":
        return MockChatModel(model_name=effective_model)

    if effective_provider == "openai":
        if not settings.OPENAI_API_KEY.strip():
            logger.info("OPENAI_API_KEY missing; agent LLM falling back to mock")
            return MockChatModel(model_name=effective_model)
        try:
            from langchain_openai import ChatOpenAI  # type: ignore import-not-found
        except ImportError as exc:
            logger.warning("langchain-openai not installed (%s); falling back to mock", exc)
            return MockChatModel(model_name=effective_model)
        try:
            model = ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or None,
                model=effective_model,
                timeout=settings.CHAT_REQUEST_TIMEOUT,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to construct ChatOpenAI: %s", exc)
            return MockChatModel(model_name=effective_model)
        return _LangChainChatModel(model, provider="openai", model_name=effective_model)

    if effective_provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY.strip():
            logger.info("DEEPSEEK_API_KEY missing; agent LLM falling back to mock")
            return MockChatModel(model_name=effective_model)
        try:
            from langchain_openai import ChatOpenAI  # type: ignore import-not-found
        except ImportError as exc:
            logger.warning("langchain-openai not installed (%s); falling back to mock", exc)
            return MockChatModel(model_name=effective_model)
        try:
            model = ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL.rstrip("/") + "/v1"
                if not settings.DEEPSEEK_BASE_URL.rstrip("/").endswith("/v1")
                else settings.DEEPSEEK_BASE_URL,
                model=effective_model or settings.DEEPSEEK_CHAT_MODEL,
                timeout=settings.CHAT_REQUEST_TIMEOUT,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to construct DeepSeek ChatOpenAI: %s", exc)
            return MockChatModel(model_name=effective_model)
        return _LangChainChatModel(
            model,
            provider="deepseek",
            model_name=effective_model or settings.DEEPSEEK_CHAT_MODEL,
        )

    if effective_provider == "ollama":
        return _build_ollama_model(effective_model)

    logger.info("Unknown AGENT_PROVIDER=%r; falling back to mock", effective_provider)
    return MockChatModel(model_name=effective_model)


def langchain_available() -> bool:
    """Return ``True`` when LangChain core is importable."""
    try:
        import langchain_core  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def langgraph_available() -> bool:
    """Return ``True`` when LangGraph is importable."""
    try:
        import langgraph  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def deepagents_available() -> bool:
    """Return ``True`` when DeepAgents is importable AND flag is on.

    DeepAgents remains optional; we never trigger an import unless the
    operator explicitly opted-in via ``AGENT_ENABLE_DEEPAGENTS=true``.
    """
    if not settings.AGENT_ENABLE_DEEPAGENTS:
        return False
    try:
        import deepagents  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True
