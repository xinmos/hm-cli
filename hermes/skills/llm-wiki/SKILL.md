---
name: llm-wiki
slash_command: /wiki
description: Build and maintain a persistent, interlinked markdown knowledge base. Use when the user wants to create a wiki, ingest sources, query compiled knowledge, lint for consistency, or references their wiki/knowledge base. Handles knowledge accumulation via incremental compilation rather than per-query retrieval.
allowed-tools: bash(grep:*, find:*, ls:*, cat:*, head:*, tail:*), Read, Write, Edit, Glob, WebSearch, WebFetch
---

# LLM Wiki

Build and maintain a persistent, compounding knowledge base as interlinked markdown files.
Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Unlike traditional RAG (which rediscovers knowledge from scratch per query), the wiki
compiles knowledge once and keeps it current. Cross-references are already there.
Contradictions have already been flagged. Synthesis reflects everything ingested.

**Division of labor:** The human curates sources and directs analysis. The agent
summarizes, cross-references, files, and maintains consistency.

## When This Skill Activates

This skill should be used when the user:
- Asks to create, build, or start a wiki or knowledge base
- Asks to ingest, add, or process a source into their wiki
- Asks a question and an existing wiki is present at the configured path
- Asks to lint, audit, or health-check their wiki
- References their wiki, knowledge base, or "notes" in a research context

## Wiki Location

The wiki path can be set via environment variable `LLM_WIKI_PATH` or defaults to `~/wiki`.

```bash
WIKI="${LLM_WIKI_PATH:-$HOME/wiki}"
```

The wiki is just a directory of markdown files — open it in Obsidian, VS Code, or
any editor. No database, no special tooling required.

```plain
wiki/
├── SCHEMA.md           # Conventions, structure rules, domain config
├── index.md            # Sectioned content catalog with one-line summaries
├── log.md              # Chronological action log (append-only, rotated yearly)
├── raw/                # Layer 1: Immutable source material
│   ├── articles/       # Web articles, clippings
│   ├── papers/         # PDFs, arxiv papers
│   ├── transcripts/    # Meeting notes, interviews
│   └── assets/         # Images, diagrams referenced by sources
├── entities/           # Layer 2: Entity pages (people, orgs, products, models)
├── concepts/           # Layer 2: Concept/topic pages
├── comparisons/        # Layer 2: Side-by-side analyses
└── queries/            # Layer 2: Filed query results worth keeping
```

**Layer 1** — Raw Sources: Immutable. Read but never modify these files.
**Layer 2** — The Wiki: Agent-owned markdown files. Created, updated, and cross-referenced by the agent.
**Layer 3** — The Schema: SCHEMA.md defines structure, conventions, and tag taxonomy.

## Resuming an Existing Wiki (CRITICAL — do this every session)
When the user has an existing wiki, always orient before doing anything:

1. Read SCHEMA.md — understand the domain, conventions, and tag taxonomy.
2. Read index.md — learn what pages exist and their summaries.
3. Scan recent log.md — read the last 20-30 entries to understand recent activity.

```bash
WIKI="${LLM_WIKI_PATH:-$HOME/wiki}"
# Orientation reads at session start
cat "$WIKI/SCHEMA.md"
cat "$WIKI/index.md"
tail -30 "$WIKI/log.md"
```

Only after orientation should you ingest, query, or lint. This prevents:

- Creating duplicate pages for entities that already exist 
- Missing cross-references to existing content 
- Contradicting the schema's conventions 
- Repeating work already logged

For large wikis (100+ pages), also run a grep search for the topic at hand before creating anything new.

## Initializing a New Wiki

When the user asks to create or start a wiki:

1. Determine the wiki path (from LLM_WIKI_PATH env var, or ask the user; default ~/wiki)
2. Create the directory structure above 
3. Ask the user what domain the wiki covers — be specific 
4. Write SCHEMA.md customized to the domain (see template below)
5. Write initial index.md with sectioned header 
6. Write initial log.md with creation entry 
7. Confirm the wiki is ready and suggest first sources to ingest

### SCHEMA.md Template

```markdown
# Wiki Schema

## Domain
[What this wiki covers — e.g., "AI/ML research", "personal health", "startup intelligence"]

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md` under the correct section
- Every action must be appended to `log.md`

## Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  type: entity | concept | comparison | query | summary
  tags: [from taxonomy below]
  sources: [raw/articles/source-name.md]
  contradictions: [page-name]  # optional: pages with conflicting claims
  ---
```

### Tag Taxonomy
[Define 10-20 top-level tags for the domain. Add new tags here BEFORE using them.]

Example for AI/ML:

- Models: model, architecture, benchmark, training 
- People/Orgs: person, company, lab, open-source 
- Techniques: optimization, fine-tuning, inference, alignment, data 
- Meta: comparison, timeline, controversy, prediction 
- Rule: every tag on a page must appear in this taxonomy.

### Page Thresholds

- Create a page when an entity/concept appears in 2+ sources OR is central to one source 
- Add to existing page when a source mentions something already covered 
- DON'T create a page for passing mentions, minor details, or things outside the domain 
- Split a page when it exceeds ~200 lines — break into sub-topics with cross-links 
- Archive a page when its content is fully superseded — move to _archive/, remove from index

### Entity Pages
One page per notable entity. Include:

- Overview / what it is 
- Key facts and dates 
- Relationships to other entities ([[wikilinks]])
-Source references

### Concept Pages
One page per concept or topic. Include:

- Definition / explanation 
- Current state of knowledge 
- Open questions or debates 
- Related concepts ([[wikilinks]])


### Comparison Pages
Side-by-side analyses. Include:

- What is being compared and why 
- Dimensions of comparison (table format preferred)
- Verdict or synthesis 
- Sources

## Update Policy
When new information conflicts with existing content:

1. Check the dates — newer sources generally supersede older ones 
2. If genuinely contradictory, note both positions with dates and sources 
3. Mark the contradiction in frontmatter: contradictions: [page-name]
4. Flag for user review in the lint report

```text

### index.md Template

```markdown
# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: YYYY-MM-DD | Total pages: N

## Entities
<!-- Alphabetical within section -->

## Concepts

## Comparisons

## Queries
```

### log.md Template

```markdown
# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> When this file exceeds 500 entries, rotate: rename to log-YYYY.md, start fresh.

## [YYYY-MM-DD] create | Wiki initialized
- Domain: [domain]
- Structure created with SCHEMA.md, index.md, log.md
```

## Core Operations

### 1. Ingest
When the user provides a source (URL, file, paste), integrate it into the wiki:

1. Capture the raw source — save to appropriate raw/ subdirectory with descriptive name.
2. Discuss takeaways with the user — what's interesting, what matters for the domain.
3. Check what already exists — grep index.md and search for existing pages for mentioned entities/concepts.
4. Write or update wiki pages:
   - New entities/concepts: Create pages only if they meet Page Thresholds 
   - Existing pages: Add new information, bump updated date 
   - Cross-reference: Minimum 2 wikilinks per page 
   - Tags: Only use tags from SCHEMA.md taxonomy
5. Update navigation:
   - Add new pages to index.md 
   - Update "Total pages" and "Last updated" in index header 
   - Append to log.md: ## [YYYY-MM-DD] ingest | Source Title
6. Report what changed — list every file created or updated.

### 2. Query
When the user asks a question about the wiki's domain:

1. Read index.md to identify relevant pages.
2. For large wikis, grep across all .md files for key terms.
3. Read relevant pages and synthesize an answer with citations.
4. File valuable answers back to queries/ or comparisons/.
5. Update log.md.

### 3. Lint
When the user asks to lint, health-check, or audit the wiki:

1. Orphan pages: Find pages with no inbound wikilinks. 
2. Broken wikilinks: Find links to non-existent pages. 
3. Index completeness: Verify every wiki page appears in index.md. 
4. Frontmatter validation: All required fields present, tags in taxonomy. 
5. Stale content: Pages with updated >90 days older than most recent source. 
6. Contradictions: Pages sharing tags/entities with conflicting claims. 
7. Page size: Flag pages over 200 lines for splitting. 
8. Tag audit: List all tags, flag any not in taxonomy. 
9. Log rotation: Rotate if log.md exceeds 500 entries. 
10. Report findings grouped by severity. 
11. Append to log.md.

## Pitfalls
Never modify raw/ — sources are immutable.

- Always orient first — read SCHEMA + index + recent log before any operation. 
- Always update index.md and log.md — these are the navigational backbone. 
- Don't create pages for passing mentions — follow Page Thresholds. 
- Every page must have at least 2 wikilinks — isolated pages are invisible. 
- Frontmatter is required — enables search, filtering, staleness detection. 
- Tags must come from the taxonomy — add new tags to SCHEMA.md first. 
- Keep pages scannable — split pages over 200 lines. 
- Handle contradictions explicitly — note both claims with dates, mark in frontmatter.








