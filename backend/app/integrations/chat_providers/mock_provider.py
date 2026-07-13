"""
Mock chat provider for local UI validation.
"""
from app.integrations.chat_providers.base import BaseChatProvider, ChatCompletionResult


class MockChatProvider(BaseChatProvider):
    provider_name = "mock"

    def __init__(self) -> None:
        self.model_name = "mock-chat"

    def chat(self, question: str, *, history: list[dict[str, str]] | None = None) -> ChatCompletionResult:
        turn_count = len(history or []) // 2
        answer = (
            "这是本地验证用的 mock chat provider。"
            f" 当前收到的问题是：{question}"
            f" 既有上下文轮数：{turn_count}。"
        )
        return ChatCompletionResult(
            provider=self.provider_name,
            model_name=self.model_name,
            answer=answer,
        )

    def stream_chat(self, question: str, *, history: list[dict[str, str]] | None = None):
        result = self.chat(question, history=history)
        chunks = [
            "这是本地验证用的 mock chat provider。",
            f" 当前收到的问题是：{question}",
            f" 既有上下文轮数：{len(history or []) // 2}。",
        ]

        def iterator():
            for chunk in chunks:
                yield chunk

        return iterator()
