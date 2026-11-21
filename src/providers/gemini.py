"""Google Gemini provider implementation"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import BaseProvider, ProviderResponse

if TYPE_CHECKING:
    from ..utils.config import ProviderConfig


class GeminiProvider(BaseProvider):
    """Provider for Google's Gemini models"""

    name = "gemini"
    color = "cyan"

    def __init__(self, config: ProviderConfig, timeout: int = 30):
        super().__init__(config, timeout)
        self._client = None

    def _get_client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            try:
                from google import genai

                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY environment variable not set")
                self._client = genai.Client(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. Run: pip install google-genai"
                )
        return self._client

    async def _make_request(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> ProviderResponse:
        """Make async request to Gemini API"""
        try:
            from google.genai import types

            client = self._get_client()

            # Build config
            config = types.GenerateContentConfig(
                max_output_tokens=self.config.max_tokens,
            )
            if self.config.temperature is not None:
                config.temperature = self.config.temperature
            if system:
                config.system_instruction = system

            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg["content"])],
                    )
                )

            response = await client.aio.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config,
            )

            # Extract content
            content = response.text or ""

            # Extract token usage
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

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
