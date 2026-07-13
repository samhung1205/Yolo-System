"""
Models API route — returns available LLM providers and their model lists.

The availability of each provider is determined by the current `.env`:
- openai / deepseek: available when the corresponding API key is set.
- ollama: always listed; model list is fetched live from the local Ollama
  daemon. If the daemon is unreachable, the configured default model is
  returned as a fallback.
- mock: intentionally omitted (internal testing only).
"""
from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderModelList(BaseModel):
    provider: str
    label: str
    models: list[str]
    available: bool = True
    """False when the provider's API key is not configured; models are shown
    as read-only placeholders so the user knows what to configure."""


def _strip_latest(name: str) -> str:
    """Remove the ':latest' tag that Ollama appends by default."""
    return name[:-7] if name.endswith(":latest") else name


def _fetch_ollama_models() -> list[str]:
    """Query Ollama /api/tags for installed models. Returns fallback on error."""
    try:
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        resp = httpx.get(f"{base}/api/tags", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            names = [_strip_latest(m.get("name", "")) for m in data.get("models", [])]
            names = [n for n in names if n]
            if names:
                return names
    except Exception:
        logger.debug("Ollama unreachable — using configured default model")
    default = _strip_latest(settings.OLLAMA_MODEL.strip() or "llama3.2")
    return [default]


@router.get("", response_model=list[ProviderModelList])
def list_available_models(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProviderModelList]:
    """Return all LLM providers.

    Providers without a configured API key are included with ``available=False``
    so the frontend can display them as "needs configuration" rather than hiding
    them entirely.
    """
    result: list[ProviderModelList] = []

    openai_key = settings.OPENAI_API_KEY.strip()
    configured_model = settings.OPENAI_CHAT_MODEL.strip() or "gpt-4.1-mini"
    openai_models = [configured_model]
    for extra in ("gpt-4.1-mini", "gpt-4o", "gpt-4-turbo", "gpt-4"):
        if extra not in openai_models:
            openai_models.append(extra)
    result.append(ProviderModelList(
        provider="openai",
        label="OpenAI GPT",
        models=openai_models,
        available=bool(openai_key),
    ))

    deepseek_key = settings.DEEPSEEK_API_KEY.strip()
    configured_ds = settings.DEEPSEEK_CHAT_MODEL.strip() or "deepseek-chat"
    deepseek_models = [configured_ds]
    for extra in ("deepseek-chat", "deepseek-coder", "deepseek-reasoner"):
        if extra not in deepseek_models:
            deepseek_models.append(extra)
    result.append(ProviderModelList(
        provider="deepseek",
        label="DeepSeek",
        models=deepseek_models,
        available=bool(deepseek_key),
    ))

    ollama_models = _fetch_ollama_models()
    result.append(ProviderModelList(
        provider="ollama",
        label="Ollama (本地)",
        models=ollama_models,
        available=True,
    ))

    return result
