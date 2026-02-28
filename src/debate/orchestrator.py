"""Main debate orchestrator"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from ..providers import AnthropicProvider, GroqProvider, OpenAIProvider
from ..providers.base import BaseProvider
from ..utils.costs import CostTracker
from .phases import DebatePhase, PhaseManager, PhaseResult
from .voting import VoteResults, VotingSystem

if TYPE_CHECKING:
    from ..utils.config import Config


@dataclass
class DebateResult:
    """Complete result of a debate"""

    question: str
    started_at: datetime
    completed_at: datetime | None = None
    phases: dict[str, PhaseResult] = field(default_factory=dict)
    vote_results: VoteResults | None = None
    verdict: str = ""
    participating_providers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cost_summary: dict | None = None

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def success(self) -> bool:
        return self.verdict != "" and len(self.errors) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        phases_dict = {}
        for phase_name, phase_result in self.phases.items():
            phases_dict[phase_name] = {
                "responses": {
                    name: {
                        "content": resp.content,
                        "input_tokens": resp.input_tokens,
                        "output_tokens": resp.output_tokens,
                        "error": resp.error,
                        "latency_ms": resp.latency_ms,
                    }
                    for name, resp in phase_result.responses.items()
                },
                "duration_seconds": phase_result.duration_seconds,
                "errors": phase_result.errors,
            }

        return {
            "question": self.question,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "participating_providers": self.participating_providers,
            "phases": phases_dict,
            "vote_results": (
                self.vote_results.to_dict() if self.vote_results else None
            ),
            "verdict": self.verdict,
            "errors": self.errors,
            "cost_summary": self.cost_summary,
        }


class DebateOrchestrator:
    """Orchestrates the entire debate process"""

    PROVIDER_CLASSES = {
        "claude": AnthropicProvider,
        "openai": OpenAIProvider,
        "groq": GroqProvider,
    }

    def __init__(
        self,
        config: Config,
        progress_callback: Callable[[str, str, str], None] | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            config: Configuration object
            progress_callback: Optional callback(phase, provider, status)
        """
        self.config = config
        self.progress_callback = progress_callback
        self.providers: dict[str, BaseProvider] = {}
        self.cost_tracker = CostTracker(config.costs)

        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize enabled providers"""
        for provider_config in self.config.get_enabled_providers():
            provider_class = self.PROVIDER_CLASSES.get(provider_config.name)
            if provider_class:
                provider = provider_class(
                    provider_config, timeout=self.config.debate.timeout
                )
                provider.set_retry_config(
                    self.config.debate.max_retries,
                    self.config.debate.retry_delay,
                )
                self.providers[provider_config.name] = provider

    def _phase_progress_callback(
        self, phase: str
    ) -> Callable[[str, str], None]:
        """Create a progress callback for a specific phase"""
        def callback(provider: str, status: str) -> None:
            if self.progress_callback:
                self.progress_callback(phase, provider, status)

        return callback

    async def run_debate(self, question: str) -> DebateResult:
        """Run a complete debate on the given question"""
        result = DebateResult(
            question=question,
            started_at=datetime.now(),
            participating_providers=list(self.providers.keys()),
        )

        if len(self.providers) < 2:
            result.errors.append(
                f"Need at least 2 providers for a debate, got {len(self.providers)}"
            )
            result.completed_at = datetime.now()
            return result

        # Create phase manager
        phase_manager = PhaseManager(
            providers=self.providers,
            cost_tracker=self.cost_tracker,
            progress_callback=self._phase_progress_callback(""),
        )

        try:
            # Phase 1: Initial responses
            phase_manager.progress_callback = self._phase_progress_callback(
                "initial"
            )
            initial_result = await phase_manager.run_initial_phase(question)
            result.phases["initial"] = initial_result
            result.errors.extend(initial_result.errors)

            # Check if we have enough responses to continue
            if len(initial_result.get_successful_responses()) < 2:
                result.errors.append("Not enough successful initial responses")
                result.completed_at = datetime.now()
                return result

            # Phase 2: Cross-review
            phase_manager.progress_callback = self._phase_progress_callback(
                "review"
            )
            review_result = await phase_manager.run_review_phase(question)
            result.phases["review"] = review_result
            result.errors.extend(review_result.errors)

            # Phase 3: Final positions
            phase_manager.progress_callback = self._phase_progress_callback(
                "final"
            )
            final_result = await phase_manager.run_final_phase(question)
            result.phases["final"] = final_result
            result.errors.extend(final_result.errors)

            # Phase 3.5: Voting
            phase_manager.progress_callback = self._phase_progress_callback(
                "voting"
            )
            voting_result = await phase_manager.run_voting_phase(question)
            result.phases["voting"] = voting_result

            # Process votes
            voting_system = VotingSystem(list(self.providers.keys()))
            for name, response in voting_result.responses.items():
                vote = voting_system.parse_vote(name, response)
                if vote:
                    voting_system.record_vote(vote)

            result.vote_results = voting_system.get_results()

            # Phase 4: Verdict
            phase_manager.progress_callback = self._phase_progress_callback(
                "verdict"
            )
            vote_tallies = {
                "best_overall": result.vote_results.best_overall_tally,
                "most_accurate": result.vote_results.most_accurate_tally,
                "most_practical": result.vote_results.most_practical_tally,
            }
            verdict_result = await phase_manager.run_verdict_phase(
                question, vote_tallies
            )
            result.phases["verdict"] = verdict_result

            if "verdict" in verdict_result.responses:
                result.verdict = verdict_result.responses["verdict"].content

            # Add cost summary
            result.cost_summary = {
                "total_cost": self.cost_tracker.total_cost,
                "total_tokens": self.cost_tracker.total_tokens,
                "by_provider": self.cost_tracker.get_provider_summary(),
                "warning": self.cost_tracker.is_over_threshold(),
            }

        except Exception as e:
            result.errors.append(f"Debate error: {str(e)}")

        result.completed_at = datetime.now()
        return result

    def get_cost_summary(self) -> str:
        """Get formatted cost summary"""
        return self.cost_tracker.format_summary()
