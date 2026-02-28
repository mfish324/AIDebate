#!/usr/bin/env python3
"""
Multi-AI Debate System

A CLI application that orchestrates debates between multiple AI providers:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Llama (Groq)

Usage:
    python debate.py "What's the best database for a startup?"
    python debate.py --interactive
    python debate.py --models claude,openai "question here"
    python debate.py --verbose "question here"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.debate.orchestrator import DebateOrchestrator
from src.output.console import ConsoleOutput
from src.output.json_export import JSONExporter
from src.output.markdown import MarkdownExporter
from src.utils.config import load_config

app = typer.Typer(
    name="debate",
    help="Multi-AI Debate System - Orchestrate debates between AI providers",
    add_completion=False,
)
console = Console()


def parse_models(models_str: str | None) -> list[str] | None:
    """Parse comma-separated model list"""
    if not models_str:
        return None
    return [m.strip().lower() for m in models_str.split(",")]


def run_debate_async(
    question: str,
    config_path: str | None,
    models: list[str] | None,
    exclude: list[str] | None,
    output_dir: str,
    formats: list[str],
    verbose: bool,
    quiet: bool,
) -> None:
    """Run the debate (async wrapper)"""
    asyncio.run(
        _run_debate(
            question=question,
            config_path=config_path,
            models=models,
            exclude=exclude,
            output_dir=output_dir,
            formats=formats,
            verbose=verbose,
            quiet=quiet,
        )
    )


async def _run_debate(
    question: str,
    config_path: str | None,
    models: list[str] | None,
    exclude: list[str] | None,
    output_dir: str,
    formats: list[str],
    verbose: bool,
    quiet: bool,
) -> None:
    """Run the actual debate"""
    # Load configuration
    config = load_config(config_path)

    # Apply model filters
    if models:
        config.enable_only(models)
    if exclude:
        config.exclude_providers(exclude)

    # Override output settings
    config.output.directory = output_dir
    config.output.verbose = verbose

    # Setup console output
    console_output = ConsoleOutput(verbose=verbose, quiet=quiet)

    # Print header
    console_output.print_header(question)

    # Check enabled providers
    enabled = config.get_enabled_providers()
    if len(enabled) < 2:
        console_output.print_error(
            f"Need at least 2 providers for a debate. "
            f"Enabled: {[p.name for p in enabled]}"
        )
        raise typer.Exit(1)

    # Create progress callback
    current_phase = {"name": ""}

    def progress_callback(phase: str, provider: str, status: str) -> None:
        if phase != current_phase["name"]:
            if current_phase["name"]:
                console_output.stop_phase_progress()
            current_phase["name"] = phase
            provider_names = [p.name for p in enabled]
            console_output.start_phase_progress(phase, provider_names)
        console_output.update_progress(provider, status)

    # Create orchestrator
    orchestrator = DebateOrchestrator(
        config=config,
        progress_callback=progress_callback,
    )

    # Run debate
    try:
        result = await orchestrator.run_debate(question)
    finally:
        console_output.stop_phase_progress()

    # Print results
    console_output.print_result(result)

    # Save outputs
    saved_files = []

    if "md" in formats:
        md_exporter = MarkdownExporter(output_dir)
        md_path = md_exporter.export(result)
        saved_files.append(md_path)

    if "json" in formats:
        json_exporter = JSONExporter(output_dir)
        json_path = json_exporter.export(result)
        saved_files.append(json_path)

    for filepath in saved_files:
        console_output.print_save_location(filepath)


def interactive_mode(
    config_path: str | None,
    models: list[str] | None,
    exclude: list[str] | None,
    output_dir: str,
    formats: list[str],
    verbose: bool,
) -> None:
    """Run in interactive mode"""
    console.print("[bold]🤖 Multi-AI Debate System - Interactive Mode[/bold]")
    console.print("[dim]Type 'exit' or 'quit' to end the session[/dim]\n")

    while True:
        try:
            question = Prompt.ask("[bold blue]Enter your question[/bold blue]")

            if question.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if not question.strip():
                console.print("[yellow]Please enter a question[/yellow]")
                continue

            run_debate_async(
                question=question,
                config_path=config_path,
                models=models,
                exclude=exclude,
                output_dir=output_dir,
                formats=formats,
                verbose=verbose,
                quiet=False,
            )
            console.print("\n" + "=" * 60 + "\n")

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@app.command()
def main(
    question: Optional[str] = typer.Argument(
        None,
        help="The question to debate",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Run in interactive mode",
    ),
    models: Optional[str] = typer.Option(
        None,
        "--models",
        "-m",
        help="Comma-separated list of models to use (e.g., 'claude,openai')",
    ),
    exclude: Optional[str] = typer.Option(
        None,
        "--exclude",
        "-x",
        help="Comma-separated list of models to exclude (e.g., 'groq')",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom config file",
    ),
    output: str = typer.Option(
        "debates",
        "--output",
        "-o",
        help="Output directory for saved debates",
    ),
    format: str = typer.Option(
        "md",
        "--format",
        "-f",
        help="Output formats (comma-separated: md,json)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full API responses",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Only show final verdict",
    ),
) -> None:
    """
    Multi-AI Debate System

    Orchestrate debates between Claude, GPT-4, and Llama.
    Each AI provides initial responses, reviews others' answers,
    submits final positions, votes, and a verdict is synthesized.

    Examples:

        python debate.py "What's the best database for a startup?"

        python debate.py --interactive

        python debate.py --models claude,openai "Your question"

        python debate.py --exclude groq --verbose "Your question"
    """
    # Parse format list
    formats = [f.strip().lower() for f in format.split(",")]

    # Parse model lists
    models_list = parse_models(models)
    exclude_list = parse_models(exclude)

    if interactive:
        interactive_mode(
            config_path=config,
            models=models_list,
            exclude=exclude_list,
            output_dir=output,
            formats=formats,
            verbose=verbose,
        )
    elif question:
        run_debate_async(
            question=question,
            config_path=config,
            models=models_list,
            exclude=exclude_list,
            output_dir=output,
            formats=formats,
            verbose=verbose,
            quiet=quiet,
        )
    else:
        console.print("[yellow]Please provide a question or use --interactive mode[/yellow]")
        console.print("\nUsage: python debate.py [OPTIONS] QUESTION")
        console.print("       python debate.py --interactive")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
