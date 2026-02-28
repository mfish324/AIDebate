"""Anthropic Claude provider implementation"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import BaseProvider, ProviderResponse

if TYPE_CHECKING:
    from ..utils.config import ProviderConfig


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic's Claude models"""

    name = "claude"
    color = "purple"

    def __init__(self, config: ProviderConfig, timeout: int = 30):
        super().__init__(config, timeout)
        self._client = None

    def _get_client(self):
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            try:
                import anthropic

                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environment variable not set")
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    async def _make_request(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> ProviderResponse:
        """Make async request to Claude API"""
        try:
            client = self._get_client()

            # Build request kwargs
            kwargs = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "messages": messages,
            }

            if system:
                kwargs["system"] = system

            if self.config.temperature is not None:
                kwargs["temperature"] = self.config.temperature

            response = await client.messages.create(**kwargs)

            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text

            return ProviderResponse(
                provider=self.name,
                content=content,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self.config.model,
            )

        except Exception as e:
            return ProviderResponse(
                provider=self.name,
                content="",
                error=str(e),
            )
