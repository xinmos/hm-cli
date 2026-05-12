# hm-cli (Hermes CLI)

AI-powered CLI companion. Built for humans, driven by intelligence.

## Quick Start

```bash
# Install dependencies
uv sync

# Run CLI mode
uv run cli.py

# Run QQ bot mode
uv run python cli.py qq

# Run Feishu bot mode
uv run python cli.py feishu
```

## Run Web mode

```bash
# one terminal starts backend + frontend
uv run python cli.py web

# or
./web/start-dev.sh
```

Press `Ctrl+C` in that terminal to stop both services together.

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
HERMES_LLM_WIKI_PATH=.hermes/llm-wiki  # Optional llm-wiki knowledge base path

# Optional: Context Management
HERMES_CONTEXT_THRESHOLD=30
HERMES_CONTEXT_MAX=50
HERMES_TASKS_PATH=.hermes/tasks.json

# Optional: Debug
HERMES_DEBUG=1

# Optional: QQ official bot channel
HERMES_QQ_APP_ID=your-qq-bot-app-id
HERMES_QQ_SECRET=your-qq-bot-app-secret
HERMES_QQ_SANDBOX=false
HERMES_QQ_ENABLE_GUILD=true
HERMES_QQ_ENABLE_DIRECT=true
HERMES_QQ_ENABLE_GROUP=true
HERMES_QQ_ENABLE_C2C=true
HERMES_QQ_ENABLE_MARKDOWN=true

# Optional: Feishu/Lark bot channel
HERMES_FEISHU_APP_ID=your-feishu-app-id
HERMES_FEISHU_APP_SECRET=your-feishu-app-secret
HERMES_FEISHU_DOMAIN=https://open.feishu.cn
HERMES_FEISHU_AUTO_RECONNECT=true
HERMES_FEISHU_ENABLE_MARKDOWN=true
HERMES_FEISHU_ENABLE_STREAMING=true
```

QQ and Feishu bot settings can also be saved from the Web UI in Settings ->
Channel Configuration. Environment variables still take precedence over saved
values. Feishu streaming replies use CardKit markdown cards and require the
`cardkit:card:write` permission in the Feishu developer console.

You can also persist the llm-wiki path in `.hermes/settings.json`:

```json
{
  "llm_wiki": {
    "path": "~/Documents/obisidian-llm"
  }
}
```

The built-in `llm-wiki` skill can initialize that directory on a new machine
from bundled templates. In chat, ask Hermes to initialize llm-wiki, or ask a
question with "通过知识库回答" to have it use the configured knowledge base.

## Philosophy

- **Simple**: Complex things made easy
- **Extensible**: Skill-based architecture, add what you need
- **Human-centric**: AI assists, you decide
