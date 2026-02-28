"""Base provider class and response models"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..utils.config import ProviderConfig


@dataclass
class ProviderResponse:
    """Response from an AI provider"""

    provider: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    error: str | None = None
    latency_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None and self.content != ""


class BaseProvider(ABC):
    """Abstract base class for AI providers"""

    name: str = "base"
    color: str = "white"

    def __init__(self, config: ProviderConfig, timeout: int = 30):
        self.config = config
        self.timeout = timeout
        self._retry_count = 0
        self._max_retries = 3
        self._retry_delay = 1.0

    def set_retry_config(self, max_retries: int, retry_delay: float) -> None:
        """Configure retry behavior"""
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    @abstractmethod
    async def _make_request(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> ProviderResponse:
        """Make the actual API request - implemented by subclasses"""
        pass

    async def complete(
        self, messages: list[dict[str, str]], system: str | None = None
    ) -> ProviderResponse:
        """Complete a chat request with retry logic"""
        last_error = None

        for attempt in range(self._max_retries):
            try:
                start_time = datetime.now()
                response = await asyncio.wait_for(
                    self._make_request(messages, system),
                    timeout=self.timeout,
                )
                response.latency_ms = (
                    datetime.now() - start_time
                ).total_seconds() * 1000
                return response

            except asyncio.TimeoutError:
                last_error = f"Request timed out after {self.timeout}s"
            except Exception as e:
                last_error = str(e)

            if attempt < self._max_retries - 1:
                delay = self._retry_delay * (2**attempt)  # Exponential backoff
                await asyncio.sleep(delay)

        return ProviderResponse(
            provider=self.name,
            content="",
            error=f"Failed after {self._max_retries} attempts: {last_error}",
        )

    def format_prompt_initial(self, question: str) -> list[dict[str, str]]:
        """Format prompt for initial response phase"""
        return [{"role": "user", "content": question}]

    def format_prompt_review(
        self,
        question: str,
        own_response: str,
        other_responses: dict[str, str],
    ) -> list[dict[str, str]]:
        """Format prompt for cross-review phase"""
        others_text = "\n\n".join(
            f"**{name}'s response:**\n{response}"
            for name, response in other_responses.items()
        )

        content = f"""Original question: {question}

Your initial response: {own_response}

Other AI responses to review:
{others_text}

Please analyze the other responses. For each:
1. Identify strengths and valid points
2. Point out any errors, gaps, or weaknesses
3. Note where you agree or disagree

Be constructive but thorough in your critique."""

        return [{"role": "user", "content": content}]

    def format_prompt_final(
        self,
        question: str,
        own_response: str,
        own_review: str,
        other_reviews: dict[str, str],
    ) -> list[dict[str, str]]:
        """Format prompt for final position phase"""
        reviews_text = "\n\n".join(
            f"**{name}'s review of others:**\n{review}"
            for name, review in other_reviews.items()
        )

        content = f"""Original question: {question}

Your initial response: {own_response}

Your review of others: {own_review}

Other AIs' reviews:
{reviews_text}

Based on all the discussion, provide your FINAL answer:
1. State your most confident answer to the original question
2. Acknowledge any valid points from others you now incorporate
3. Provide counter-arguments against positions you still disagree with
4. Summarize your key takeaways"""

        return [{"role": "user", "content": content}]

    def format_prompt_vote(
        self,
        question: str,
        all_final_responses: dict[str, str],
    ) -> list[dict[str, str]]:
        """Format prompt for voting phase"""
        responses_text = "\n\n".join(
            f"**{name}'s final answer:**\n{response}"
            for name, response in all_final_responses.items()
        )

        # Get other provider names (can't vote for self)
        other_providers = [p for p in all_final_responses.keys() if p != self.name]

        content = f"""Original question: {question}

All final answers:
{responses_text}

You must vote for the best responses. You CANNOT vote for yourself ({self.name}).
Choose from: {', '.join(other_providers)}

Provide your votes in this EXACT format:
BEST_OVERALL: [provider name]
MOST_ACCURATE: [provider name]
MOST_PRACTICAL: [provider name]

Then briefly explain each vote (1-2 sentences each)."""

        return [{"role": "user", "content": content}]

    def format_prompt_verdict(
        self,
        question: str,
        all_responses: dict[str, dict[str, str]],
        vote_results: dict[str, dict[str, int]],
    ) -> list[dict[str, str]]:
        """Format prompt for synthesizing final verdict"""
        # Format all phase responses
        phases_text = ""
        for phase in ["initial", "review", "final"]:
            phases_text += f"\n### {phase.title()} Phase:\n"
            for name, phases in all_responses.items():
                if phase in phases:
                    phases_text += f"**{name}:** {phases[phase][:500]}...\n\n"

        # Format vote results
        votes_text = "\nVoting Results:\n"
        for category, votes in vote_results.items():
            votes_text += f"  {category}: "
            votes_text += ", ".join(f"{p}: {v} votes" for p, v in votes.items())
            votes_text += "\n"

        content = f"""As a neutral synthesizer, analyze this debate and provide a final verdict.

Original question: {question}

{phases_text}

{votes_text}

Provide a comprehensive verdict:
1. CONSENSUS POINTS: What did all AIs agree on?
2. KEY DISPUTES: Where did they fundamentally disagree?
3. BEST OVERALL ANSWER: Synthesize the strongest arguments into a final answer
4. CONFIDENCE LEVEL: How certain is this conclusion? (High/Medium/Low)"""

        return [{"role": "user", "content": content}]
