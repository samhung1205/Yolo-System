"""
DeepSeek provider compatibility layer for backend chat service.
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


class DeepSeekChatProvider(BaseChatProvider):
    provider_name = "deepseek"

    def __init__(self) -> None:
        self.api_key = settings.DEEPSEEK_API_KEY.strip()
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.model_name = settings.DEEPSEEK_CHAT_MODEL.strip()
        self.system_prompt = settings.CHAT_SYSTEM_PROMPT.strip()
        self.timeout = settings.CHAT_REQUEST_TIMEOUT

        if not self.api_key:
            raise ChatProviderConfigurationError("DEEPSEEK_API_KEY 未設定，無法使用 DeepSeek chat provider")
        if not self.model_name:
            raise ChatProviderConfigurationError("DEEPSEEK_CHAT_MODEL 未設定，無法使用 DeepSeek chat provider")

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ChatProviderRequestError(f"DeepSeek request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ChatProviderRequestError(_extract_error_message(response))

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ChatProviderRequestError("DeepSeek returned an invalid JSON response") from exc

        answer = _extract_answer_text(data)
        if not answer:
            raise ChatProviderRequestError("DeepSeek response did not include assistant content")

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        def iterator():
            try:
                with httpx.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
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
            except httpx.HTTPError as exc:
                raise ChatProviderRequestError(f"DeepSeek request failed: {exc}") from exc

        return iterator()


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return f"DeepSeek request failed with status {response.status_code}"

    error_obj = payload.get("error")
    if isinstance(error_obj, dict):
        message = error_obj.get("message")
        if message:
            return f"DeepSeek request failed: {message}"

    detail = payload.get("detail")
    if isinstance(detail, str) and detail:
        return f"DeepSeek request failed: {detail}"

    return f"DeepSeek request failed with status {response.status_code}"


def _extract_answer_text(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    return ""


def _extract_stream_delta(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return ""

    content = delta.get("content")
    if isinstance(content, str):
        return content

    return ""
