# hm-cli (Hermes CLI)

AI-powered CLI companion. Built for humans, driven by intelligence.

## Quick Start

```bash
# Install dependencies
uv sync

# Run CLI mode
uv run cli.py
```

## Run Web mode (need two terminals)
```bash
# backend
uv run python -m uvicorn web.backend.main:app --reload --port 8000

# frontend
cd web/frontend && npm run dev
```

## Environment Variables

Create `.env` file in project root:

```bash
# Required: LLM Configuration
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# Optional: Model Parameters
TEMPERATURE=0.7
MAX_TOKENS=2048
CONTEXT_WINDOW=256

# Optional: Behavior Settings
HERMES_WORKDIR=.          # Working directory
HERMES_TIMEOUT=120        # Command timeout (seconds)
HERMES_MAX_OUTPUT=50000   # Max output chars
HERMES_MAX_LINES=500      # Max output lines
HERMES_STRICT=true        # Strict sandbox mode

# Optional: Context Management
HERMES_CONTEXT_THRESHOLD=30
HERMES_CONTEXT_MAX=50
HERMES_TASKS_PATH=.hermes/tasks.json

# Optional: Debug
HERMES_DEBUG=1
```

## Philosophy

- **Simple**: Complex things made easy
- **Extensible**: Skill-based architecture, add what you need
- **Human-centric**: AI assists, you decide
