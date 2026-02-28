"""Debate phase implementations"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..providers.base import BaseProvider, ProviderResponse
    from ..utils.costs import CostTracker


class DebatePhase(Enum):
    """Enum for debate phases"""

    INITIAL = "initial"
    REVIEW = "review"
    FINAL = "final"
    VOTING = "voting"
    VERDICT = "verdict"


@dataclass
class PhaseResult:
    """Result of a single phase"""

    phase: DebatePhase
    responses: dict[str, ProviderResponse] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def get_successful_responses(self) -> dict[str, str]:
        """Get content from successful responses only"""
        return {
            name: resp.content
            for name, resp in self.responses.items()
            if resp.success
        }


class PhaseManager:
    """Manages execution of debate phases"""

    def __init__(
        self,
        providers: dict[str, BaseProvider],
        cost_tracker: CostTracker | None = None,
        progress_callback: Callable[[str, str], None] | None = None,
    ):
        self.providers = providers
        self.cost_tracker = cost_tracker
        self.progress_callback = progress_callback
        self.phase_results: dict[DebatePhase, PhaseResult] = {}

    def _notify_progress(self, provider: str, status: str) -> None:
        """Notify progress callback if set"""
        if self.progress_callback:
            self.progress_callback(provider, status)

    def _record_usage(self, response: ProviderResponse) -> None:
        """Record token usage if cost tracker is set"""
        if self.cost_tracker and response.success:
            self.cost_tracker.record_usage(
                response.provider,
                response.input_tokens,
                response.output_tokens,
            )

    async def run_initial_phase(self, question: str) -> PhaseResult:
        """Phase 1: Each AI answers independently"""
        result = PhaseResult(phase=DebatePhase.INITIAL)

        system_prompt = (
            "You are participating in a multi-AI debate. Provide a thoughtful, "
            "well-reasoned response to the question. Be specific and support "
            "your points with examples or evidence where possible."
        )

        async def get_response(name: str, provider: BaseProvider) -> None:
            self._notify_progress(name, "thinking")
            messages = provider.format_prompt_initial(question)
            response = await provider.complete(messages, system=system_prompt)
            result.responses[name] = response
            self._record_usage(response)
            if response.error:
                result.errors.append(f"{name}: {response.error}")
            self._notify_progress(name, "done" if response.success else "error")

        # Run all providers in parallel
        await asyncio.gather(
            *[get_response(name, p) for name, p in self.providers.items()]
        )

        result.completed_at = datetime.now()
        self.phase_results[DebatePhase.INITIAL] = result
        return result

    async def run_review_phase(self, question: str) -> PhaseResult:
        """Phase 2: Each AI reviews others' responses"""
        result = PhaseResult(phase=DebatePhase.REVIEW)

        initial = self.phase_results.get(DebatePhase.INITIAL)
        if not initial:
            result.errors.append("Initial phase not completed")
            return result

        initial_responses = initial.get_successful_responses()

        system_prompt = (
            "You are reviewing other AI responses in a debate. Be fair and "
            "constructive in your critique. Acknowledge good points while "
            "identifying any weaknesses or gaps in reasoning."
        )

        async def get_review(name: str, provider: BaseProvider) -> None:
            self._notify_progress(name, "reviewing")

            own_response = initial_responses.get(name, "")
            other_responses = {
                k: v for k, v in initial_responses.items() if k != name
            }

            if not other_responses:
                result.errors.append(f"{name}: No other responses to review")
                self._notify_progress(name, "error")
                return

            messages = provider.format_prompt_review(
                question, own_response, other_responses
            )
            response = await provider.complete(messages, system=system_prompt)
            result.responses[name] = response
            self._record_usage(response)
            if response.error:
                result.errors.append(f"{name}: {response.error}")
            self._notify_progress(name, "done" if response.success else "error")

        # Only review if there were successful initial responses
        if len(initial_responses) >= 2:
            await asyncio.gather(
                *[get_review(name, p) for name, p in self.providers.items()]
            )

        result.completed_at = datetime.now()
        self.phase_results[DebatePhase.REVIEW] = result
        return result

    async def run_final_phase(self, question: str) -> PhaseResult:
        """Phase 3: Each AI submits final position"""
        result = PhaseResult(phase=DebatePhase.FINAL)

        initial = self.phase_results.get(DebatePhase.INITIAL)
        review = self.phase_results.get(DebatePhase.REVIEW)

        if not initial or not review:
            result.errors.append("Previous phases not completed")
            return result

        initial_responses = initial.get_successful_responses()
        review_responses = review.get_successful_responses()

        system_prompt = (
            "Provide your final, most confident answer after considering all "
            "perspectives. Synthesize the best ideas while addressing any valid "
            "criticisms of your position."
        )

        async def get_final(name: str, provider: BaseProvider) -> None:
            self._notify_progress(name, "finalizing")

            own_response = initial_responses.get(name, "")
            own_review = review_responses.get(name, "")
            other_reviews = {
                k: v for k, v in review_responses.items() if k != name
            }

            messages = provider.format_prompt_final(
                question, own_response, own_review, other_reviews
            )
            response = await provider.complete(messages, system=system_prompt)
            result.responses[name] = response
            self._record_usage(response)
            if response.error:
                result.errors.append(f"{name}: {response.error}")
            self._notify_progress(name, "done" if response.success else "error")

        await asyncio.gather(
            *[get_final(name, p) for name, p in self.providers.items()]
        )

        result.completed_at = datetime.now()
        self.phase_results[DebatePhase.FINAL] = result
        return result

    async def run_voting_phase(self, question: str) -> PhaseResult:
        """Phase 3.5: Each AI votes on best responses"""
        result = PhaseResult(phase=DebatePhase.VOTING)

        final = self.phase_results.get(DebatePhase.FINAL)
        if not final:
            result.errors.append("Final phase not completed")
            return result

        final_responses = final.get_successful_responses()

        if len(final_responses) < 2:
            result.errors.append("Not enough responses to vote on")
            return result

        system_prompt = (
            "Vote honestly based on the quality of arguments, not loyalty. "
            "Consider accuracy, clarity, and practical value."
        )

        async def get_vote(name: str, provider: BaseProvider) -> None:
            self._notify_progress(name, "voting")

            messages = provider.format_prompt_vote(question, final_responses)
            response = await provider.complete(messages, system=system_prompt)
            result.responses[name] = response
            self._record_usage(response)
            if response.error:
                result.errors.append(f"{name}: {response.error}")
            self._notify_progress(name, "done" if response.success else "error")

        await asyncio.gather(
            *[get_vote(name, p) for name, p in self.providers.items()]
        )

        result.completed_at = datetime.now()
        self.phase_results[DebatePhase.VOTING] = result
        return result

    async def run_verdict_phase(
        self, question: str, vote_results: dict
    ) -> PhaseResult:
        """Phase 4: Synthesize final verdict (uses first available provider)"""
        result = PhaseResult(phase=DebatePhase.VERDICT)

        # Gather all responses from all phases
        all_responses: dict[str, dict[str, str]] = {}
        for phase in [DebatePhase.INITIAL, DebatePhase.REVIEW, DebatePhase.FINAL]:
            phase_result = self.phase_results.get(phase)
            if phase_result:
                for name, resp in phase_result.responses.items():
                    if name not in all_responses:
                        all_responses[name] = {}
                    if resp.success:
                        all_responses[name][phase.value] = resp.content

        # Use first available provider for synthesis
        provider_name, provider = next(iter(self.providers.items()))
        self._notify_progress(provider_name, "synthesizing")

        system_prompt = (
            "As a neutral judge, synthesize the debate into a clear verdict. "
            "Be balanced and acknowledge the merits of all positions."
        )

        messages = provider.format_prompt_verdict(
            question, all_responses, vote_results
        )
        response = await provider.complete(messages, system=system_prompt)
        result.responses["verdict"] = response
        self._record_usage(response)

        if response.error:
            result.errors.append(f"Verdict: {response.error}")

        self._notify_progress(provider_name, "done" if response.success else "error")

        result.completed_at = datetime.now()
        self.phase_results[DebatePhase.VERDICT] = result
        return result

    def get_all_results(self) -> dict[DebatePhase, PhaseResult]:
        """Get all phase results"""
        return self.phase_results
