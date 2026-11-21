# AIDebate - Multi-AI Debate Orchestrator

## Overview

Python CLI app that orchestrates structured debates between four AI providers: Claude (Anthropic), GPT-4 (OpenAI), Gemini (Google), and Llama (Groq). AIs answer a question, critique each other, refine positions, vote, and synthesize a verdict.

## Tech Stack

- Python 3.10+ with async/await
- Typer (CLI), Rich (terminal UI)
- AI SDKs: anthropic, openai, google-genai, groq
- PyYAML for config, python-dotenv for env vars

## Project Structure

```
debate.py                    # CLI entry point
config.yaml                  # Provider models, timeouts, cost pricing
src/
  debate/
    orchestrator.py          # DebateOrchestrator - main debate runner
    phases.py                # PhaseManager - 5-phase debate flow
    voting.py                # VotingSystem - vote parsing & tallying
  providers/
    base.py                  # BaseProvider ABC with retry/backoff
    anthropic.py             # Claude provider
    openai.py                # OpenAI GPT provider
    gemini.py                # Google Gemini provider
    groq.py                  # Groq Llama provider
  output/
    console.py               # Rich console UI
    markdown.py              # Markdown export
    json_export.py           # JSON export
  utils/
    config.py                # Config loading (YAML + defaults)
    costs.py                 # Token usage & cost tracking
debates/                     # Saved debate output files
```

## Current Models (updated 2026-03-31)

- **Claude**: `claude-sonnet-4-6`
- **OpenAI**: `gpt-4.1`
- **Gemini**: `gemini-2.5-flash`
- **Groq**: `llama-4-scout-17b-16e-instruct`

Models are configured in two places (keep in sync):
- `config.yaml` — runtime config
- `src/utils/config.py` `get_default_config()` — fallback defaults

## Key Commands

```bash
# Run a debate
python debate.py "Your question here"

# Interactive mode
python debate.py --interactive

# Select specific models
python debate.py --models claude,openai "question"

# Verbose / quiet
python debate.py --verbose "question"
python debate.py --quiet "question"

# Custom config / output
python debate.py --config my_config.yaml --output ./my_debates --format md,json "question"
```

## Debate Flow (5 phases)

1. **Initial Responses** — each AI answers independently (parallel async)
2. **Cross-Review** — each AI critiques the other two
3. **Final Positions** — each AI refines their answer
4. **Voting** — each AI votes on best/most accurate/most practical (no self-voting)
5. **Verdict** — one AI synthesizes consensus, disputes, and final answer

## API Keys

Required env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`

## Architecture Notes

- Providers use lazy client initialization and async clients
- Retry with exponential backoff (configurable in config.yaml)
- Minimum 2 providers required to run a debate
- Exports to both Markdown and JSON in `debates/` directory
- Cost tracking with per-provider token pricing
