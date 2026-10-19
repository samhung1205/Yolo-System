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

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.services.llm_policy import allowed_models

router = APIRouter()


class ProviderModelList(BaseModel):
    provider: str
    label: str
    models: list[str]
    available: bool = True
    """False when the provider's API key is not configured; models are shown
    as read-only placeholders so the user knows what to configure."""


@router.get("", response_model=list[ProviderModelList])
def list_available_models(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProviderModelList]:
    """Return all LLM providers with the models a client is allowed to pick.

    The lists come from the same allowlist that ``/api/chat`` and
    ``/api/agent`` enforce (``app/services/llm_policy.py``). Providers without
    a configured API key are included with ``available=False`` so the frontend
    can display them as "needs configuration" rather than hiding them entirely.
    """
    return [
        ProviderModelList(
            provider="openai",
            label="OpenAI GPT",
            models=allowed_models("openai"),
            available=bool(settings.OPENAI_API_KEY.strip()),
        ),
        ProviderModelList(
            provider="deepseek",
            label="DeepSeek",
            models=allowed_models("deepseek"),
            available=bool(settings.DEEPSEEK_API_KEY.strip()),
        ),
        ProviderModelList(
            provider="ollama",
            label="Ollama (本地)",
            models=allowed_models("ollama"),
            available=True,
        ),
    ]
