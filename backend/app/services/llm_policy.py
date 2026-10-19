"""
LLM access policy shared by ``/api/chat`` and ``/api/agent``.

- Provider / model allowlist: a client may only pick a provider we support
  and a model on that provider's allowlist, so a logged-in user cannot point
  our paid API keys at an arbitrary (expensive) model.
- Per-user rate limits: a per-minute budget across every LLM endpoint plus a
  daily cap for paid providers.

The limiter is in-process memory. That matches the current single-worker
deployment; running several uvicorn workers multiplies the effective limits
and would need a shared store (e.g. Redis) instead.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

KNOWN_PROVIDERS = frozenset({"openai", "deepseek", "ollama", "mock"})
PAID_PROVIDERS = frozenset({"openai", "deepseek"})

DEFAULT_OPENAI_MODELS = ("gpt-4.1-mini", "gpt-4o")
DEFAULT_DEEPSEEK_MODELS = ("deepseek-chat", "deepseek-reasoner")

OLLAMA_TAGS_CACHE_SECONDS = 30.0


@dataclass(frozen=True)
class LlmSelection:
    provider: str
    model: str


# --------------------------------------------------------------------------
# Allowlist
# --------------------------------------------------------------------------


def _is_production() -> bool:
    return settings.is_production


def _strip_latest(name: str) -> str:
    """Ollama reports ``name:latest``; clients use the bare name."""
    return name[: -len(":latest")] if name.endswith(":latest") else name


def _dedupe(values) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


_ollama_cache: dict[str, object] = {"expires_at": 0.0, "models": []}
_ollama_cache_lock = threading.Lock()


def fetch_ollama_models() -> list[str]:
    """Installed Ollama models (``/api/tags``), cached briefly. Empty if unreachable."""
    now = time.monotonic()
    with _ollama_cache_lock:
        if now < float(_ollama_cache["expires_at"]):
            return list(_ollama_cache["models"])  # type: ignore[arg-type]

    models: list[str] = []
    try:
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        response = httpx.get(f"{base}/api/tags", timeout=3)
        if response.status_code == 200:
            models = _dedupe(
                _strip_latest(entry.get("name", "")) for entry in response.json().get("models", [])
            )
    except Exception:
        logger.debug("Ollama unreachable while listing models")

    with _ollama_cache_lock:
        _ollama_cache["models"] = models
        _ollama_cache["expires_at"] = now + OLLAMA_TAGS_CACHE_SECONDS
    return list(models)


def provider_default_model(provider: str) -> str:
    if provider == "openai":
        return settings.OPENAI_CHAT_MODEL.strip() or "gpt-4.1-mini"
    if provider == "deepseek":
        return settings.DEEPSEEK_CHAT_MODEL.strip() or "deepseek-chat"
    if provider == "ollama":
        return _strip_latest(settings.OLLAMA_MODEL.strip() or "llama3.2")
    return "mock-chat"


def allowed_models(provider: str) -> list[str]:
    """Models a client may request for ``provider``; the default comes first."""
    default = provider_default_model(provider)
    if provider == "openai":
        return _dedupe([default, *(settings.OPENAI_ALLOWED_MODELS or DEFAULT_OPENAI_MODELS)])
    if provider == "deepseek":
        return _dedupe([default, *(settings.DEEPSEEK_ALLOWED_MODELS or DEFAULT_DEEPSEEK_MODELS)])
    if provider == "ollama":
        installed = fetch_ollama_models()
        return installed or [default]
    if provider == "mock":
        return [default]
    return []


def _provider_allowed(provider: str) -> bool:
    if provider not in KNOWN_PROVIDERS:
        return False
    if provider == "mock" and _is_production():
        return False
    return True


def resolve_llm_selection(
    provider_override: Optional[str],
    model_override: Optional[str],
    *,
    default_provider: str,
    default_model: Optional[str] = None,
) -> LlmSelection:
    """Validate a client's provider/model choice and fill in defaults.

    ``default_model`` is the model to use when the client stays on
    ``default_provider`` without naming a model (the agent has its own
    AGENT_MODEL). Switching provider without a model picks that provider's
    configured default, never the other provider's model name.
    """
    fallback_provider = (default_provider or "mock").strip().lower()
    provider = (provider_override or "").strip().lower() or fallback_provider
    if not _provider_allowed(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支援的模型供應商：{provider}",
        )

    model = (model_override or "").strip()
    if model:
        allowed = allowed_models(provider)
        if _strip_latest(model) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模型 {model} 不在 {provider} 的允許清單內",
            )
        return LlmSelection(provider=provider, model=_strip_latest(model))

    if provider == fallback_provider and (default_model or "").strip():
        return LlmSelection(provider=provider, model=default_model.strip())
    return LlmSelection(provider=provider, model=provider_default_model(provider))


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


class LlmRateLimitExceeded(Exception):
    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = max(1, int(retry_after_seconds))


class LlmRateLimiter:
    """Per-user sliding minute window + per-user daily cap for paid providers."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._minute_hits: dict[int, deque[float]] = {}
        self._daily_day: str = ""
        self._daily_counts: dict[int, int] = {}

    def check_and_record(
        self,
        user_id: int,
        provider: str,
        *,
        per_minute: int,
        paid_daily: int,
    ) -> None:
        now = self._clock()
        today = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
        is_paid = provider in PAID_PROVIDERS

        with self._lock:
            if today != self._daily_day:
                self._daily_day = today
                self._daily_counts = {}

            hits = self._minute_hits.setdefault(user_id, deque())
            while hits and hits[0] <= now - 60:
                hits.popleft()

            if per_minute > 0 and len(hits) >= per_minute:
                retry_after = math.ceil(hits[0] + 60 - now)
                raise LlmRateLimitExceeded("AI 請求太頻繁，請稍後再試。", retry_after)

            if is_paid and paid_daily > 0 and self._daily_counts.get(user_id, 0) >= paid_daily:
                tomorrow = (math.floor(now / 86400) + 1) * 86400
                raise LlmRateLimitExceeded(
                    "今日付費模型的使用額度已用完，請改用本地模型或明天再試。",
                    math.ceil(tomorrow - now),
                )

            hits.append(now)
            if is_paid:
                self._daily_counts[user_id] = self._daily_counts.get(user_id, 0) + 1

    def reset(self) -> None:
        with self._lock:
            self._minute_hits.clear()
            self._daily_counts.clear()
            self._daily_day = ""


llm_rate_limiter = LlmRateLimiter()


def authorize_llm_request(
    *,
    user_id: int,
    provider_override: Optional[str],
    model_override: Optional[str],
    default_provider: str,
    default_model: Optional[str] = None,
) -> LlmSelection:
    """Resolve the provider/model for a request and charge it to the user's budget."""
    selection = resolve_llm_selection(
        provider_override,
        model_override,
        default_provider=default_provider,
        default_model=default_model,
    )
    try:
        llm_rate_limiter.check_and_record(
            user_id,
            selection.provider,
            per_minute=settings.LLM_RATE_LIMIT_PER_MINUTE,
            paid_daily=settings.LLM_PAID_DAILY_LIMIT,
        )
    except LlmRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return selection
