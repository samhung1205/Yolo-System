"""
Ollama local chat provider.

Ollama exposes an OpenAI-compatible REST API at ``/v1/chat/completions``.
No API key is required. Uses ``httpx`` (already in requirements) — no extra
package needed.

Reference: https://ollama.com/blog/openai-compatibility
"""
import json

import httpx

from app.core.config import settings
from app.integrations.chat_providers.base import (
    BaseChatProvider,
    ChatCompletionResult,
    ChatProviderConfigurationError,
    ChatProviderRequestError,
)


class OllamaChatProvider(BaseChatProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.base_url = (settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        self.model_name = (settings.OLLAMA_MODEL or "llama3.2").strip()
        self.system_prompt = settings.CHAT_SYSTEM_PROMPT.strip()
        self.timeout = max(settings.CHAT_REQUEST_TIMEOUT, 120)  # local models can be slow

        if not self.model_name:
            raise ChatProviderConfigurationError("OLLAMA_MODEL 未設定，無法使用 Ollama chat provider")

    def chat(self, question: str, *, history: list[dict[str, str]] | None = None) -> ChatCompletionResult:
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except httpx.ConnectError as exc:
            raise ChatProviderRequestError(
                f"無法連線到 Ollama ({self.base_url})。請確認 Ollama 已啟動：ollama serve"
            ) from exc
        except httpx.HTTPError as exc:
            raise ChatProviderRequestError(f"Ollama request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ChatProviderRequestError(_extract_error_message(response))

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ChatProviderRequestError("Ollama returned an invalid JSON response") from exc

        answer = _extract_answer_text(data)
        if not answer:
            raise ChatProviderRequestError("Ollama response did not include assistant content")

        return ChatCompletionResult(
            provider=self.provider_name,
            model_name=data.get("model") or self.model_name,
            answer=answer,
        )

    def stream_chat(self, question: str, *, history: list[dict[str, str]] | None = None):
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        headers = {"Content-Type": "application/json"}

        def iterator():
            try:
                with httpx.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                ) as response:
                    if response.status_code >= 400:
                        raise ChatProviderRequestError(_extract_error_message(response))

                    for line in response.iter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            payload_obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta = _extract_stream_delta(payload_obj)
                        if delta:
                            yield delta
            except httpx.ConnectError as exc:
                raise ChatProviderRequestError(
                    f"無法連線到 Ollama ({self.base_url})。請確認 Ollama 已啟動：ollama serve"
                ) from exc
            except httpx.HTTPError as exc:
                raise ChatProviderRequestError(f"Ollama stream failed: {exc}") from exc

        return iterator()


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return f"Ollama request failed with status {response.status_code}"

    error_obj = payload.get("error")
    if isinstance(error_obj, dict):
        message = error_obj.get("message")
        if message:
            return f"Ollama request failed: {message}"
    if isinstance(error_obj, str) and error_obj:
        return f"Ollama request failed: {error_obj}"

    return f"Ollama request failed with status {response.status_code}"


def _extract_answer_text(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _extract_stream_delta(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""
