"""Voting and scoring system for debates"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers.base import ProviderResponse


@dataclass
class Vote:
    """A single vote from one AI"""

    voter: str
    best_overall: str
    most_accurate: str
    most_practical: str
    explanation: str = ""


@dataclass
class VoteResults:
    """Aggregated voting results"""

    votes: list[Vote] = field(default_factory=list)
    best_overall_tally: dict[str, int] = field(default_factory=dict)
    most_accurate_tally: dict[str, int] = field(default_factory=dict)
    most_practical_tally: dict[str, int] = field(default_factory=dict)

    def add_vote(self, vote: Vote) -> None:
        """Add a vote and update tallies"""
        self.votes.append(vote)

        # Update tallies
        if vote.best_overall:
            self.best_overall_tally[vote.best_overall] = (
                self.best_overall_tally.get(vote.best_overall, 0) + 1
            )
        if vote.most_accurate:
            self.most_accurate_tally[vote.most_accurate] = (
                self.most_accurate_tally.get(vote.most_accurate, 0) + 1
            )
        if vote.most_practical:
            self.most_practical_tally[vote.most_practical] = (
                self.most_practical_tally.get(vote.most_practical, 0) + 1
            )

    def get_winner(self, category: str) -> tuple[str, int]:
        """Get winner of a category and their vote count"""
        tally = getattr(self, f"{category}_tally", {})
        if not tally:
            return ("", 0)
        winner = max(tally, key=tally.get)
        return (winner, tally[winner])

    def get_overall_winner(self) -> str:
        """Get overall winner based on combined votes"""
        combined: dict[str, int] = {}
        for tally in [
            self.best_overall_tally,
            self.most_accurate_tally,
            self.most_practical_tally,
        ]:
            for provider, count in tally.items():
                combined[provider] = combined.get(provider, 0) + count

        if not combined:
            return ""
        return max(combined, key=combined.get)

    def calculate_confidence(self) -> float:
        """Calculate confidence score based on agreement (0-1)"""
        if not self.votes:
            return 0.0

        # Check how much the votes agree
        agreement_score = 0.0
        total_categories = 3

        for tally in [
            self.best_overall_tally,
            self.most_accurate_tally,
            self.most_practical_tally,
        ]:
            if tally:
                max_votes = max(tally.values())
                total_votes = sum(tally.values())
                if total_votes > 0:
                    agreement_score += max_votes / total_votes

        return agreement_score / total_categories

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        return {
            "votes": [
                {
                    "voter": v.voter,
                    "best_overall": v.best_overall,
                    "most_accurate": v.most_accurate,
                    "most_practical": v.most_practical,
                    "explanation": v.explanation,
                }
                for v in self.votes
            ],
            "tallies": {
                "best_overall": self.best_overall_tally,
                "most_accurate": self.most_accurate_tally,
                "most_practical": self.most_practical_tally,
            },
            "overall_winner": self.get_overall_winner(),
            "confidence_score": self.calculate_confidence(),
        }


class VotingSystem:
    """Manages the voting process"""

    def __init__(self, provider_names: list[str]):
        self.provider_names = provider_names
        self.results = VoteResults()

    def parse_vote(self, voter: str, response: ProviderResponse) -> Vote | None:
        """Parse a vote from an AI's response"""
        if not response.success:
            return None

        content = response.content.upper()

        # Parse each vote category
        best_overall = self._extract_vote(content, "BEST_OVERALL")
        most_accurate = self._extract_vote(content, "MOST_ACCURATE")
        most_practical = self._extract_vote(content, "MOST_PRACTICAL")

        # Validate votes (can't vote for self)
        valid_targets = [p for p in self.provider_names if p != voter]

        if best_overall and best_overall.lower() not in [
            v.lower() for v in valid_targets
        ]:
            best_overall = ""
        if most_accurate and most_accurate.lower() not in [
            v.lower() for v in valid_targets
        ]:
            most_accurate = ""
        if most_practical and most_practical.lower() not in [
            v.lower() for v in valid_targets
        ]:
            most_practical = ""

        # Normalize case
        best_overall = self._normalize_provider_name(best_overall)
        most_accurate = self._normalize_provider_name(most_accurate)
        most_practical = self._normalize_provider_name(most_practical)

        return Vote(
            voter=voter,
            best_overall=best_overall,
            most_accurate=most_accurate,
            most_practical=most_practical,
            explanation=response.content,
        )

    def _extract_vote(self, content: str, category: str) -> str:
        """Extract a vote from the response content"""
        # Look for pattern like "BEST_OVERALL: claude" or "BEST_OVERALL: [claude]"
        pattern = rf"{category}:\s*\[?(\w+)\]?"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _normalize_provider_name(self, name: str) -> str:
        """Normalize provider name to lowercase"""
        if not name:
            return ""

        name_lower = name.lower()

        # Handle common variations
        name_map = {
            "claude": "claude",
            "anthropic": "claude",
            "openai": "openai",
            "gpt": "openai",
            "gpt4": "openai",
            "gpt-4": "openai",
            "groq": "groq",
            "llama": "groq",
        }

        return name_map.get(name_lower, name_lower)

    def record_vote(self, vote: Vote) -> None:
        """Record a vote in the results"""
        self.results.add_vote(vote)

    def get_results(self) -> VoteResults:
        """Get the voting results"""
        return self.results
