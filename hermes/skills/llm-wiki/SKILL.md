---
name: llm-wiki
description: Operate an Obsidian-based LLM Wiki workspace. Use when the user wants to ingest raw sources, query the knowledge base, lint it, or says "通过知识库回答"/"基于知识库回答"/"根据知识库".
allowed-tools: init_llm_wiki, Bash(test:*), Bash(mkdir:*), Bash(ls:*), Bash(find:*), Bash(grep:*), Bash(cat:*), Bash(head:*), Bash(tail:*), Read, Write, Edit
---

# LLM Wiki

You manage an Obsidian-based LLM Wiki workspace. The workspace is initialized
once from bundled templates, then reused across sessions.

## Active Path

Hermes injects the configured wiki path here:

```text
{{LLM_WIKI_PATH}}
```

In examples:

```bash
WIKI_ROOT="{{LLM_WIKI_PATH}}"
```

## Initialize

If the workspace is missing or incomplete, do not explain the internal template
layout. Tell the user to open 设置 → 知识库 and click
"初始化知识库". If the user explicitly asks you to initialize from chat or CLI,
call `init_llm_wiki`; it creates only missing files/directories and never
overwrites existing user files.

## Session Startup

Before ingesting, querying, or linting, orient yourself:

1. Read `purpose.md`.
2. Read `wiki/index.md`.
3. Read recent `wiki/log.md` entries.
4. If creating or updating pages, read `schema/prompt.md`.
5. Check `raw/sources/` for unprocessed material when ingesting.

If required files are missing, ask the user to initialize from Settings before
continuing, unless they explicitly ask you to run `init_llm_wiki`.

## Architecture

The workspace has three layers:

| Layer | Path | Rule |
|-------|------|------|
| Raw Sources | `raw/sources/` | Human-owned, read-only. Never modify raw sources. |
| Wiki | `wiki/` | Agent-owned structured markdown. |
| Schema | `schema/prompt.md`, `purpose.md` | Operating spec and research direction. |

Every page in `wiki/` must have YAML frontmatter with one of these `type`
values:

- `source`
- `entity`
- `concept`
- `synthesis`
- `comparison`
- `query`

Follow the detailed schemas in `schema/prompt.md`.

## Query

When the user says "通过知识库回答", "基于知识库回答", "根据知识库", or asks
about the knowledge base:

1. Run the session startup ritual.
2. Use `wiki/index.md` to find candidate pages.
3. Search `wiki/` for the user’s key terms when needed.
4. Read relevant pages and synthesize an answer.
5. Cite internal knowledge with Obsidian links like `[[concepts/memdir|memdir]]`.
6. If the answer is valuable, ask whether to archive it under `wiki/queries/`.

## Ingest

When the user asks you to process material in `raw/sources/`:

1. Read the raw source. Never edit files under `raw/sources/`.
2. Identify entities, concepts, core claims, contradictions, and links to
   existing wiki pages.
3. Create or update:
   - `wiki/sources/<slug>.md`
   - relevant `wiki/entities/`
   - relevant `wiki/concepts/`
   - `wiki/synthesis/` or `wiki/comparisons/` if warranted
4. Update `wiki/index.md`.
5. Append to `wiki/log.md`.
6. Update `wiki/overview.md`.

## Lint

When the user asks to check the knowledge base:

1. Find orphan pages and pages with weak internal links.
2. Check missing or invalid YAML frontmatter.
3. Check pages absent from `wiki/index.md`.
4. Look for unresolved contradictions and stale summaries.
5. Report findings grouped by severity.
6. Append the lint action to `wiki/log.md`.

## Hard Constraints

- Never modify `raw/sources/`.
- Never overwrite existing files during initialization.
- Never delete existing wiki information unless the user explicitly confirms.
- Never copy raw source text verbatim into wiki pages; distill and restructure.
- Never create isolated wiki pages; every durable page should link to 2-3
  related pages or include clear review notes for missing links.
