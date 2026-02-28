# 🤖 Multi-AI Debate System

A Python CLI application that orchestrates debates between multiple AI providers:
- **Claude** (Anthropic) - claude-sonnet-4-20250514
- **GPT-4** (OpenAI) - gpt-4o
- **Llama** (Groq) - llama-3.3-70b-versatile

## Features

- **4-Phase Debate Flow**: Initial responses → Cross-review → Final positions → Verdict
- **Async API Calls**: Parallel requests for speed with progress indicators
- **Configurable Models**: YAML config file with CLI overrides
- **Voting System**: AIs vote on best answers with confidence scoring
- **Beautiful Output**: Rich console UI with colors, tables, and panels
- **Export Options**: Save debates as Markdown and/or JSON
- **Error Resilience**: Retry logic with exponential backoff
- **Cost Tracking**: Estimate token usage and API costs

## Installation

```bash
# Clone or navigate to the project
cd multi_ai_debate

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### API Keys

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."
```

On Windows:
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:OPENAI_API_KEY="sk-..."
$env:GROQ_API_KEY="gsk_..."
```

### Config File

Edit `config.yaml` to customize settings:

```yaml
providers:
  claude:
    enabled: true
    model: claude-sonnet-4-20250514
    max_tokens: 1000
    temperature: 0.7
  openai:
    enabled: true
    model: gpt-4o
    max_tokens: 1000
  groq:
    enabled: true
    model: llama-3.3-70b-versatile
    max_tokens: 1000

debate:
  timeout: 30
  max_retries: 3

output:
  directory: debates
  formats: [md, json]
```

## Usage

### Basic Usage

```bash
python debate.py "What's the best database for a startup?"
```

### Interactive Mode

```bash
python debate.py --interactive
python debate.py -i
```

### Select Specific Models

```bash
# Only use Claude and OpenAI
python debate.py --models claude,openai "Your question"

# Exclude Groq
python debate.py --exclude groq "Your question"
```

### Control Output

```bash
# Verbose mode (show full responses)
python debate.py --verbose "Your question"

# Quiet mode (only show verdict)
python debate.py --quiet "Your question"

# Custom output directory and formats
python debate.py --output ./my_debates --format md,json "Your question"
```

### Custom Config

```bash
python debate.py --config my_config.yaml "Your question"
```

## Debate Flow

### Phase 1: Initial Responses
Each AI independently answers the question.

### Phase 2: Cross-Review
Each AI reviews and critiques the other two responses:
- Identifies strengths and valid points
- Points out errors or gaps
- Notes agreements and disagreements

### Phase 3: Final Positions
Each AI submits their most confident answer:
- Acknowledges valid points from others
- Provides counter-arguments
- Summarizes key takeaways

### Phase 4: Voting
Each AI votes (can't vote for self):
- Best overall answer
- Most accurate response
- Most practical response

### Phase 5: Verdict
A final synthesis including:
- Consensus points
- Key disputes
- Best overall answer
- Confidence level

## Output Example

```
╭──────────────────────────────────────────────────────────╮
│  🤖 MULTI-AI DEBATE                                      │
│  Claude vs GPT-4 vs Llama                                │
╰──────────────────────────────────────────────────────────╯

❓ Question: Should startups bootstrap or raise VC funding?

━━━ Phase 1: Initial Responses ━━━
  ● Claude ━━━━━━━━━━━━━━━━━━━━ 100%
  ● GPT-4  ━━━━━━━━━━━━━━━━━━━━ 100%
  ● Llama  ━━━━━━━━━━━━━━━━━━━━ 100%

━━━ Voting Results ━━━
┌─────────────────┬─────────┬─────────┬─────────┐
│ Category        │ Claude  │ GPT-4   │ Llama   │
├─────────────────┼─────────┼─────────┼─────────┤
│ Best Overall    │ 1 vote  │ 2 votes │ 0 votes │
│ Most Accurate   │ 2 votes │ 0 votes │ 1 vote  │
│ Most Practical  │ 0 votes │ 1 vote  │ 2 votes │
└─────────────────┴─────────┴─────────┴─────────┘

━━━ Final Verdict ━━━
╭──────────────────────────────────────────────────────────╮
│ [Synthesized best answer...]                             │
╰──────────────────────────────────────────────────────────╯

💾 Saved to: debates/debate_2024-01-15_14-30-22_startups-bootstrap-vc.md
💰 Estimated cost: $0.04
```

## Project Structure

```
multi_ai_debate/
├── debate.py              # Main CLI entry point
├── config.yaml            # Default configuration
├── requirements.txt       # Dependencies
├── README.md              # This file
├── src/
│   ├── __init__.py
│   ├── providers/         # AI provider implementations
│   │   ├── __init__.py
│   │   ├── base.py        # Abstract provider class
│   │   ├── anthropic.py   # Claude provider
│   │   ├── openai.py      # GPT-4 provider
│   │   └── groq.py        # Llama provider
│   ├── debate/            # Debate logic
│   │   ├── __init__.py
│   │   ├── orchestrator.py  # Main debate runner
│   │   ├── phases.py        # Phase implementations
│   │   └── voting.py        # Voting system
│   ├── output/            # Output formatters
│   │   ├── __init__.py
│   │   ├── markdown.py    # Markdown export
│   │   ├── json_export.py # JSON export
│   │   └── console.py     # Rich console output
│   └── utils/             # Utilities
│       ├── __init__.py
│       ├── config.py      # Config loading
│       └── costs.py       # Cost tracking
└── debates/               # Saved debate outputs
```

## Customizing Models

You can easily swap models by editing `config.yaml`:

```yaml
providers:
  claude:
    model: claude-3-haiku-20240307  # Faster, cheaper
  openai:
    model: gpt-4o-mini              # Faster, cheaper
  groq:
    model: mixtral-8x7b-32768       # Alternative model
```

## Cost Tracking

The system tracks estimated costs based on token usage:

- Claude: $0.003/1K input, $0.015/1K output
- OpenAI: $0.005/1K input, $0.015/1K output
- Groq: $0.00059/1K input, $0.00079/1K output

Set a warning threshold in `config.yaml`:

```yaml
costs:
  warning_threshold: 1.00  # Warn if cost exceeds $1.00
```

## Error Handling

- **API Failures**: Continues with remaining providers
- **Timeouts**: Configurable timeout with retry logic
- **Rate Limits**: Exponential backoff for retries
- **Missing API Keys**: Clear error messages

## License

MIT License
