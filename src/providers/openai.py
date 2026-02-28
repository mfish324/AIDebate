"""OpenAI GPT provider implementation"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import BaseProvider, ProviderResponse

if TYPE_CHECKING:
    from ..utils.config import ProviderConfig


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI's GPT models"""

    name = "openai"
    color = "green"

    def __init__(self, config: ProviderConfig, timeout: int = 30):
        super().__init__(config, timeout)
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client"""
        if self._client is None:
            try:
                import openai

                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set")
                self._client = openai.AsyncOpenAI(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    async def _make_request(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> ProviderResponse:
        """Make async request to OpenAI API"""
        try:
            client = self._get_client()

            # Prepend system message if provided
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.extend(messages)

            response = await client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=full_messages,
            )

            # Extract content
            content = ""
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""

            # Extract token usage
            input_tokens = 0
            output_tokens = 0
            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            return ProviderResponse(
                provider=self.name,
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.config.model,
            )

        except Exception as e:
            return ProviderResponse(
                provider=self.name,
                content="",
                error=str(e),
            )
