# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hm-cli (Hermes CLI) is an AI-powered CLI tool built with Python. It provides an extensible agent framework with skill-based capabilities including browser automation, LLM wiki integration, and memory management.

## Common Commands

### Development

```bash
# Install dependencies
uv sync

# Run the CLI
uv run python cli.py <command>
# Or
uv run hm <command>

# Run with debug mode
HERMES_DEBUG=1 uv run python cli.py <command>

# Run in REPL mode
uv run hm chat

# Run a specific soul (agent personality)
uv run hm chat --soul claude
```

### Testing

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_agent.py

# Run a single test
uv run pytest tests/test_agent.py::test_function_name

# Run with coverage
uv run pytest --cov=hermes
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Type check
uv run pyright
```

## Architecture Overview

### Directory Structure

```
hermes/
├── app/                    # Application bootstrap and configuration
│   ├── bootstrap.py        # App initialization and DI container setup
│   ├── ports.py            # Abstract interfaces (ports in hexagonal architecture)
│   └── settings.py         # Configuration management
├── core/                   # Domain core
│   ├── agent.py            # Agent runtime and execution loop
│   ├── soul.py             # Agent personality/prompt management
│   ├── memory/             # Memory system implementation
│   └── skill_permissions.py # Skill permission management
├── infra/                  # Infrastructure implementations
│   ├── langchain/          # LangChain-based LLM backend
│   ├── persistence/        # File/JSON storage implementations
│   └── scheduler/          # APScheduler implementation
├── interfaces/             # Interface adapters
│   └── cli.py              # CLI entry point and command handlers
├── services/               # Application services
│   ├── skill_service.py    # Skill management service
│   └── task_service.py     # Task/cron management service
├── skills/                 # Skill implementations
│   ├── agent-browser/      # Browser automation skill
│   └── llm-wiki/           # LLM wiki integration skill
└── utils/                  # Utility functions
```

### Key Architectural Patterns

1. **Hexagonal Architecture (Ports and Adapters)**: Core domain logic is isolated from external concerns through ports (interfaces) in `app/ports.py`. Infrastructure implementations are in `infra/` and interface adapters in `interfaces/`.

2. **Agent Framework**: The `core/agent.py` implements an agent loop that can execute skills. Agents have a "soul" (personality/prompts defined in `core/soul.py`) and can use memory (in `core/memory/`).

3. **Skill System**: Skills are modular capabilities in `skills/`. Each skill can define its own permissions (managed by `core/skill_permissions.py`). The skill system uses LangChain tools.

4. **Memory System**: Located in `core/memory/`, provides persistent storage for agent conversations and state.

### Bootstrap Flow

1. `cli.py` calls `bootstrap_app()` from `app/bootstrap.py`
2. `ControlPlaneApp` is created with all dependencies injected
3. Settings loaded from `.hermes/` directory and `.env` file
4. Skills loaded from `skills/` directory
5. Soul (personality) loaded from `.hermes/souls/`

## Skill Development

### Creating a New Skill

1. Create a directory under `hermes/skills/<skill-name>/`
2. Add `SKILL.md` with skill definition:

```yaml
---
name: my-skill
description: What this skill does
version: 0.1.0
slash_commands:
  - command: /mycommand
    description: What this command does
    arguments: "<required> [optional]"
allowed-tools: "Bash(ls:*), Bash(cat:*), Read(*/info.md)"
---

## Instructions

What the agent should do when this skill is invoked...
```

3. Implement tools in the skill directory if needed

### Skill Permissions

Skills declare allowed tools in `SKILL.md` frontmatter:

```yaml
allowed-tools: "Bash(ls:*), Bash(cat:*), Read(*.md), WebFetch(domain:example.com)"
```

Permission patterns:
- `Bash(ls:*)` - Allow `ls` command with any args
- `Read(*/info.md)` - Allow reading `info.md` from any subdirectory
- `WebFetch(domain:github.com)` - Allow fetching only from github.com

## Security Model

The security system in `hermes/security.py` provides:

1. **Path Sandboxing**: All file paths are resolved relative to workdir and validated to prevent directory traversal
2. **Command Safety Classification**:
   - `REJECTED`: Dangerous commands (rm -rf /, sudo, etc.) - blocked immediately
   - `NEEDS_CONFIRMATION`: Potentially dangerous (rm, mv, > overwrite) - require user confirmation
   - `APPROVED`: Safe commands (ls, cat, grep, etc.) - allowed automatically

3. **Strict Mode**: When enabled, all paths must stay within workdir

## Configuration

- Environment variables loaded from `.env` file (via python-dotenv)
- App configuration stored in `.hermes/` directory
- Memory data stored in `.hermes/memory/`
- Souls (agent personalities) stored in `.hermes/souls/`

## Key Dependencies

- **LangChain/LangGraph**: Agent framework and LLM orchestration
- **Fire**: CLI command structure
- **Rich**: Terminal UI and formatting
- **ORJSON**: JSON handling (preferred over standard json)
- **APScheduler**: Background task scheduling

## Code Style Guide

This project follows strict code conventions:

1. **File Headers**: No docstrings at the top of files. First line must be import/definition.
2. **Import Order**: Standard library → Third-party → Local project. Each group separated by a blank line, alphabetically sorted within groups.
3. **Python Execution**: Always use `uv run python`, never bare `python` or `python3`.
4. **JSON**: Always use `orjson` instead of standard `json` module.
5. **Comments**: Comment "why" not "what". Explain complex logic, not obvious code.
