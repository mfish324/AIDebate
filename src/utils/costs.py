"""Cost tracking for API usage"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import CostConfig


@dataclass
class UsageRecord:
    """Record of token usage for a single API call"""

    provider: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


@dataclass
class CostTracker:
    """Track costs across multiple API calls"""

    cost_config: CostConfig
    usage_records: list[UsageRecord] = field(default_factory=list)

    def record_usage(
        self, provider: str, input_tokens: int, output_tokens: int
    ) -> UsageRecord:
        """Record token usage and calculate costs"""
        provider_costs = self.cost_config.provider_costs.get(
            provider, {"input": 0.0, "output": 0.0}
        )

        input_cost = (input_tokens / 1000) * provider_costs["input"]
        output_cost = (output_tokens / 1000) * provider_costs["output"]

        record = UsageRecord(
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
        )
        self.usage_records.append(record)
        return record

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.usage_records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.usage_records)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(r.total_cost for r in self.usage_records)

    def get_provider_summary(self) -> dict[str, dict[str, float | int]]:
        """Get usage summary by provider"""
        summary: dict[str, dict[str, float | int]] = {}

        for record in self.usage_records:
            if record.provider not in summary:
                summary[record.provider] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost": 0.0,
                }
            summary[record.provider]["input_tokens"] += record.input_tokens
            summary[record.provider]["output_tokens"] += record.output_tokens
            summary[record.provider]["total_cost"] += record.total_cost

        return summary

    def is_over_threshold(self) -> bool:
        """Check if total cost exceeds warning threshold"""
        return self.total_cost >= self.cost_config.warning_threshold

    def format_summary(self) -> str:
        """Format cost summary as string"""
        lines = ["Cost Summary:", "-" * 40]

        provider_summary = self.get_provider_summary()
        for provider, stats in provider_summary.items():
            lines.append(
                f"  {provider}: {stats['input_tokens']:,} in / "
                f"{stats['output_tokens']:,} out = ${stats['total_cost']:.4f}"
            )

        lines.append("-" * 40)
        lines.append(
            f"  Total: {self.total_input_tokens:,} in / "
            f"{self.total_output_tokens:,} out = ${self.total_cost:.4f}"
        )

        if self.is_over_threshold():
            lines.append(
                f"  ⚠️  Warning: Cost exceeds threshold "
                f"(${self.cost_config.warning_threshold:.2f})"
            )

        return "\n".join(lines)
