"""Rich console output for debates"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ..debate.orchestrator import DebateResult
    from ..debate.voting import VoteResults


# Provider color mapping
PROVIDER_COLORS = {
    "claude": "purple",
    "openai": "green",
    "groq": "orange3",
}

PROVIDER_NAMES = {
    "claude": "Claude",
    "openai": "GPT-4",
    "groq": "Llama",
}


def _safe_emoji(emoji: str, fallback: str) -> str:
    """Return emoji if supported, otherwise ASCII fallback"""
    # Check if we can encode the emoji
    try:
        emoji.encode(sys.stdout.encoding or "utf-8")
        return emoji
    except (UnicodeEncodeError, LookupError):
        return fallback


class ConsoleOutput:
    """Handles rich console output for debates"""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        # Force UTF-8 for Rich console on Windows
        self.console = Console(force_terminal=True)
        self.verbose = verbose
        self.quiet = quiet
        self._progress: Progress | None = None
        self._live: Live | None = None
        self._tasks: dict[str, int] = {}

        # Define safe symbols
        self._robot = _safe_emoji("🤖", "[AI]")
        self._question = _safe_emoji("❓", "[Q]")
        self._trophy = _safe_emoji("🏆", "[*]")
        self._money = _safe_emoji("💰", "[$]")
        self._save = _safe_emoji("💾", "[>]")
        self._error = _safe_emoji("❌", "[X]")
        self._warning = _safe_emoji("⚠️", "[!]")

    def print_header(self, question: str) -> None:
        """Print debate header"""
        if self.quiet:
            return

        header = Panel(
            Text.from_markup(
                f"[bold]{self._robot} MULTI-AI DEBATE[/bold]\n"
                "[dim]Claude vs GPT-4 vs Llama[/dim]"
            ),
            border_style="blue",
        )
        self.console.print(header)
        self.console.print()
        self.console.print(f"[bold]{self._question} Question:[/bold] {question}")
        self.console.print()

    def start_phase_progress(self, phase: str, providers: list[str]) -> None:
        """Start progress tracking for a phase"""
        if self.quiet:
            return

        phase_names = {
            "initial": "Phase 1: Initial Responses",
            "review": "Phase 2: Cross-Review",
            "final": "Phase 3: Final Positions",
            "voting": "Phase 4: Voting",
            "verdict": "Phase 5: Verdict",
        }

        self.console.print(f"\n[bold]=== {phase_names.get(phase, phase)} ===[/bold]")

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        self._tasks = {}
        for provider in providers:
            color = PROVIDER_COLORS.get(provider, "white")
            name = PROVIDER_NAMES.get(provider, provider)
            task_id = self._progress.add_task(
                f"[{color}]* {name}[/{color}]", total=100
            )
            self._tasks[provider] = task_id

        self._live = Live(self._progress, console=self.console, refresh_per_second=10)
        self._live.start()

    def update_progress(self, provider: str, status: str) -> None:
        """Update progress for a provider"""
        if not self._progress or provider not in self._tasks:
            return

        task_id = self._tasks[provider]
        if status == "thinking" or status == "reviewing" or status == "voting":
            self._progress.update(task_id, completed=50)
        elif status == "finalizing" or status == "synthesizing":
            self._progress.update(task_id, completed=75)
        elif status == "done":
            self._progress.update(task_id, completed=100)
        elif status == "error":
            self._progress.update(task_id, completed=100)
            color = PROVIDER_COLORS.get(provider, "white")
            name = PROVIDER_NAMES.get(provider, provider)
            self._progress.update(
                task_id, description=f"[{color}]* {name} [red](error)[/{color}]"
            )

    def stop_phase_progress(self) -> None:
        """Stop progress tracking"""
        if self._live:
            self._live.stop()
            self._live = None
        self._progress = None
        self._tasks = {}

    def print_phase_responses(
        self, phase: str, responses: dict[str, str]
    ) -> None:
        """Print responses from a phase"""
        if self.quiet:
            return

        if not self.verbose:
            # Just show a summary
            self.console.print(f"  [dim]({len(responses)} responses received)[/dim]")
            return

        for provider, content in responses.items():
            color = PROVIDER_COLORS.get(provider, "white")
            name = PROVIDER_NAMES.get(provider, provider)

            panel = Panel(
                Markdown(content[:1500] + ("..." if len(content) > 1500 else "")),
                title=f"[{color}]{name}[/{color}]",
                border_style=color,
            )
            self.console.print(panel)

    def print_vote_table(self, vote_results: VoteResults) -> None:
        """Print voting results as a table"""
        if self.quiet:
            return

        self.console.print("\n[bold]=== Voting Results ===[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Category", style="dim")

        # Add provider columns
        all_providers = set()
        for tally in [
            vote_results.best_overall_tally,
            vote_results.most_accurate_tally,
            vote_results.most_practical_tally,
        ]:
            all_providers.update(tally.keys())

        for provider in sorted(all_providers):
            color = PROVIDER_COLORS.get(provider, "white")
            name = PROVIDER_NAMES.get(provider, provider)
            table.add_column(name, style=color, justify="center")

        # Add rows
        def format_votes(tally: dict[str, int], providers: list[str]) -> list[str]:
            return [
                f"{tally.get(p, 0)} vote{'s' if tally.get(p, 0) != 1 else ''}"
                for p in providers
            ]

        providers_list = sorted(all_providers)
        table.add_row(
            "Best Overall",
            *format_votes(vote_results.best_overall_tally, providers_list),
        )
        table.add_row(
            "Most Accurate",
            *format_votes(vote_results.most_accurate_tally, providers_list),
        )
        table.add_row(
            "Most Practical",
            *format_votes(vote_results.most_practical_tally, providers_list),
        )

        self.console.print(table)

        # Print confidence score
        confidence = vote_results.calculate_confidence()
        confidence_text = (
            "[green]High[/green]"
            if confidence > 0.7
            else "[yellow]Medium[/yellow]"
            if confidence > 0.4
            else "[red]Low[/red]"
        )
        self.console.print(
            f"\n[dim]Agreement Level:[/dim] {confidence_text} "
            f"({confidence:.0%})"
        )

    def print_verdict(self, verdict: str) -> None:
        """Print final verdict prominently"""
        self.console.print("\n[bold]=== Final Verdict ===[/bold]")

        panel = Panel(
            Markdown(verdict),
            title=f"[bold blue]{self._trophy} VERDICT[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(panel)

    def print_cost_summary(self, cost_summary: dict) -> None:
        """Print cost summary"""
        if self.quiet:
            return

        total_cost = cost_summary.get("total_cost", 0)
        total_tokens = cost_summary.get("total_tokens", 0)
        warning = cost_summary.get("warning", False)

        text = f"{self._money} Estimated cost: ${total_cost:.4f} ({total_tokens:,} tokens)"
        if warning:
            text += f" [yellow]{self._warning} Over threshold[/yellow]"

        self.console.print(f"\n{text}")

    def print_save_location(self, filepath: str) -> None:
        """Print where the debate was saved"""
        if self.quiet:
            return

        self.console.print(f"{self._save} Saved to: [blue]{filepath}[/blue]")

    def print_error(self, message: str) -> None:
        """Print an error message"""
        self.console.print(f"[red]{self._error} Error:[/red] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message"""
        self.console.print(f"[yellow]{self._warning} Warning:[/yellow] {message}")

    def print_result(self, result: DebateResult) -> None:
        """Print complete debate result"""
        # Print vote results if available
        if result.vote_results:
            self.print_vote_table(result.vote_results)

        # Print verdict
        if result.verdict:
            self.print_verdict(result.verdict)
        elif result.errors:
            for error in result.errors:
                self.print_error(error)

        # Print cost summary
        if result.cost_summary:
            self.print_cost_summary(result.cost_summary)

        # Print duration
        if not self.quiet:
            self.console.print(
                f"\n[dim]Total time: {result.duration_seconds:.1f}s[/dim]"
            )
