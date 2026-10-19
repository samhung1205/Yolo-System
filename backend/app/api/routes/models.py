"""
Models API route — returns available LLM providers and their model lists.

The availability of each provider is determined by the current `.env`:
- openai / deepseek: available when the corresponding API key is set.
- ollama: always listed; model list is fetched live from the local Ollama
  daemon (cached briefly). If the daemon is unreachable, the configured
  default model is returned as a fallback.
- mock: intentionally omitted (internal testing only).
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.services.llm_policy import allowed_models, provider_default_model

router = APIRouter()


class ProviderModelList(BaseModel):
    provider: str
    label: str
    models: list[str]
    available: bool = True
    """False when the provider's API key is not configured; models are shown
    as read-only placeholders so the user knows what to configure."""
    is_default: bool = False
    """True for the provider the backend uses when the client sends none."""
    default_model: Optional[str] = None
    """Model the backend uses for this provider when the client sends none."""


@router.get("", response_model=list[ProviderModelList])
def list_available_models(
    _current_user: Annotated[User, Depends(get_current_user)],
    purpose: Literal["chat", "agent"] = Query(default="chat"),
) -> list[ProviderModelList]:
    """Return all LLM providers with the models a client is allowed to pick.

    The lists come from the same allowlist that ``/api/chat`` and
    ``/api/agent`` enforce (``app/services/llm_policy.py``). Providers without
    a configured API key are included with ``available=False`` so the frontend
    can display them as "needs configuration" rather than hiding them entirely.
    """
    if purpose == "agent":
        default_provider = settings.agent_effective_provider
    else:
        default_provider = settings.CHAT_PROVIDER

    def default_for(provider: str) -> str:
        if purpose == "agent" and provider == default_provider:
            return settings.agent_effective_model
        if purpose == "agent" and provider == "ollama":
            return settings.AGENT_OLLAMA_MODEL or provider_default_model("ollama")
        return provider_default_model(provider)

    def models_for(provider: str) -> list[str]:
        models = allowed_models(provider)
        preferred = default_for(provider)
        return [preferred] + [m for m in models if m != preferred] if preferred in models else models

    groups = [
        ProviderModelList(
            provider="openai",
            label="OpenAI GPT",
            models=models_for("openai"),
            available=bool(settings.OPENAI_API_KEY.strip()),
        ),
        ProviderModelList(
            provider="deepseek",
            label="DeepSeek",
            models=models_for("deepseek"),
            available=bool(settings.DEEPSEEK_API_KEY.strip()),
        ),
        ProviderModelList(
            provider="ollama",
            label="Ollama (本地)",
            models=models_for("ollama"),
            available=True,
        ),
    ]
    for group in groups:
        group.default_model = default_for(group.provider)
        group.is_default = group.provider == default_provider
    return groups
