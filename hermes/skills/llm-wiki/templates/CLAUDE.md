# CLAUDE.md

This file provides guidance to AI coding agents when working with this repository.

## Project Overview

This is an **Obsidian-based LLM Wiki**: a personal knowledge management system where the human curates raw sources and the AI organizes, summarizes, and interlinks them into a structured wiki.

The vault can be opened in Obsidian for visualization and manual browsing, but structured edits to `wiki/` are performed by the AI assistant.

## Architecture

### Three-Layer Architecture

| Layer | Path | Rule |
|-------|------|------|
| **Raw Sources** | `raw/sources/` | **Read-only**. Human places material here. Never modify. |
| **Wiki** | `wiki/` | **AI writes**. Human reads and reviews. |
| **Schema** | `schema/prompt.md`, `purpose.md` | Defines types, workflows, and conventions. |

### Page Type System

Every page in `wiki/` must have YAML frontmatter with a `type` field. Valid types:

- `source` — `wiki/sources/<slug>.md` — Summary of a raw document
- `entity` — `wiki/entities/<slug>.md` — Person, org, product, tool, place
- `concept` — `wiki/concepts/<slug>.md` — Theory, method, term
- `synthesis` — `wiki/synthesis/<slug>.md` — Cross-source narrative analysis
- `comparison` — `wiki/comparisons/<slug>.md` — Side-by-side comparison
- `query` — `wiki/queries/<slug>.md` — Archived Q&A sessions

See `schema/prompt.md` for the full frontmatter schema of each type.

### Special Files

| File | Purpose |
|------|---------|
| `purpose.md` | Goals, key questions, scope, and language preferences. Read at session start. |
| `schema/prompt.md` | The operating spec: schemas, workflows, formatting rules. |
| `wiki/index.md` | Content directory and navigation hub. Updated after every ingest. |
| `wiki/log.md` | Append-only chronological log of all operations. |
| `wiki/overview.md` | Global summary: page counts, active themes, knowledge gaps. |

## Session Startup

1. Read `purpose.md`.
2. Read `wiki/index.md`.
3. Read recent `wiki/log.md` entries.
4. Check `raw/sources/` for unprocessed material when ingesting.
5. If the task involves page creation/update, read `schema/prompt.md`.

## Core Workflows

### Ingest

Triggered when the human adds files to `raw/sources/` and asks you to process them.

1. Read the source and identify entities, concepts, core claims, contradictions, and relevant existing pages.
2. Create or update `wiki/sources/<slug>.md`.
3. Create or update relevant entity and concept pages.
4. Create synthesis or comparison pages when useful.
5. Update `wiki/index.md`.
6. Append to `wiki/log.md`.
7. Update `wiki/overview.md`.

### Query

Triggered when the human asks a question about the knowledge base.

1. Read `wiki/index.md` to locate relevant pages.
2. Search `wiki/` for key terms when needed.
3. Read relevant pages.
4. Synthesize an answer with citations like `[[concepts/example|Example]]`.
5. Ask before archiving the answer to `wiki/queries/`.

### Lint

Triggered when the human asks to check the knowledge base.

1. Scan for orphan pages and weak internal links.
2. Find missing or invalid frontmatter.
3. Check pages absent from `wiki/index.md`.
4. Identify contradictions, stale notes, and content gaps.
5. Report findings grouped by severity.

## Conventions

- Use Obsidian-style `[[wikilink]]` for internal references.
- Use `[[path/to/page|Display Name]]` for aliases.
- English filenames use kebab-case. Chinese filenames may be written directly.
- Prefer bullets over long paragraphs.
- Use ISO 8601 dates in frontmatter.
- Chinese is the default language; keep technical terms in English when clearer.

## Hard Constraints

- Never modify `raw/sources/` files.
- Never delete existing information unless explicitly confirmed as outdated.
- Never copy raw text verbatim into wiki pages; distill and restructure.
- Never create isolated pages. Durable pages should link to at least 2-3 related pages.
- Never commit `.obsidian/workspace.json`, `.obsidian/workspace-mobile.json`, `.obsidian/plugins/`, `.git/`, or system files.
