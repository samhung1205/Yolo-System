"""
Provider abstraction for cloud chat backends.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


class ChatProviderError(Exception):
    """Base exception for provider failures."""


class ChatProviderConfigurationError(ChatProviderError):
    """Raised when a provider is enabled but not configured correctly."""


class ChatProviderRequestError(ChatProviderError):
    """Raised when the upstream provider request fails."""


@dataclass(slots=True)
class ChatCompletionResult:
    provider: str
    model_name: str
    answer: str


class BaseChatProvider(ABC):
    provider_name: str

    @abstractmethod
    def chat(self, question: str, *, history: list[dict[str, str]] | None = None) -> ChatCompletionResult:
        raise NotImplementedError

    @abstractmethod
    def stream_chat(
        self,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> list[str] | tuple[str, ...] | object:
        raise NotImplementedError
