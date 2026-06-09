# Cross-Tool Memory System

**Universal Memory Layer for Developers** — Automatically captures, indexes, and makes searchable everything you do across your development tools.

## What It Does

Instead of each tool (IDE, CLI, Git) keeping its own isolated history, this system:
- **Unifies** activity from multiple sources into one local SQLite database
- **Extracts intelligence** — entities, decisions, patterns, file changes
- **Makes it searchable** — by content, time, tool, or topic
- **Surfaces context** — when you need to recall past work

## Who Is This For?

| Developer Type | Tools | Value |
|----------------|-------|-------|
| **Windsurf/Cascade** + Claude CLI | AI IDE + terminal | Full conversation history, code changes |
| **VS Code + Copilot** | Popular IDE + AI | Parse Copilot chats, VS Code logs |
| **Cursor IDE** | AI-first editor | Extract AI conversation history |
| **JetBrains + AI** | IntelliJ/PyCharm | Plugin conversation extraction |
| **Terminal-first** | vim/tmux/git/claude-cli | CLI sessions + git commits |
| **Teams** | Shared projects | Aggregate knowledge, onboarding aid |

## Use Cases

1. **Personal Knowledge** — "What was that regex I used last month?"
2. **Project Archaeology** — "Why was this architecture chosen?"
3. **Team Onboarding** — Query past decisions and patterns
4. **Pattern Recognition** — "I've solved this bug 3 times before"
5. **Auto-Documentation** — Generate decision logs from actual history

## Quick Start

```bash
# Initialize database
cd dev-memory
python3 cli.py init

# Extract data from all tools
python3 cli.py extract --all

# Search your history
python3 cli.py search "Redis race condition"

# Show recent activity
python3 cli.py recent --days 7

# View extracted entities
python3 cli.py entities

# Show active decisions
python3 cli.py decisions
```

## What It Captures

| Source | What | How |
|--------|------|-----|
| **Cascade/Windsurf** | Chat history, tool calls, file edits | Reads internal SQLite DB |
| **Claude CLI** | Conversations, project memory | Reads `~/.claude/` files |
| **Git** | Commits, file changes, diffs | `git log` with stats |

## What It Produces

- **Sessions** — unified conversation history from all tools
- **Entities** — extracted concepts (Stella, Triad, Redis, etc.)
- **Decisions** — architectural choices with context
- **Patterns** — fixes, refactors, conventions discovered
- **File Activity** — what was touched when
- **Entity Graph** — relationships between concepts

## Architecture

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Cascade   │ │ Claude CLI  │ │     Git     │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
              ┌────────┴────────┐
              │   EXTRACTORS      │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │ SQLite + vec    │
              │ (local)         │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  INTELLIGENCE   │
              │  - Entities     │
              │  - Summarize    │
              │  - Consolidate  │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  CLI / Agent    │
              └─────────────────┘
```

## Database Schema

SQLite database at `~/.dev-memory/memory.db`:

- `sessions` — raw sessions from all tools
- `turns` — individual conversation turns
- `entities` — extracted concepts with mention counts
- `entity_links` — co-occurrence relationships
- `decisions` — architectural decisions
- `patterns` — code patterns and fixes
- `file_activity` — file changes across sessions
- `session_embeddings` — semantic vectors (sqlite-vec)

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create database |
| `extract --all` | Pull from all tools |
| `search <query>` | Full-text search |
| `recent --days N` | Recent sessions |
| `entities` | Show concepts |
| `decisions` | Show active decisions |
| `stats` | Database stats |
| `related <entity>` | Entity graph |

## Cascade Integration

The `.claude/agents/memory-bridge.md` agent queries memory automatically:

```
/memory context          # Inject relevant history
/memory search <query>   # Find past sessions
```

## Differences from Cortex

| | **Cross-Tool Memory** | **Cortex** |
|---|---|---|
| **Scope** | Universal (any IDE/CLI) | Claude Code only |
| **Storage** | SQLite (simple) | PostgreSQL + pgvector |
| **Extraction** | Read-only from tools | Hooks into tool calls |
| **Consolidation** | Basic (planned) | Advanced (sleep cycles) |
| **Size** | ~500 lines Python | 8000+ lines |
| **Install** | `git clone` + `pip` | Marketplace plugin |
| **Goal** | See everything everywhere | Deep Claude integration |

This is a lightweight alternative that works across tools.

## Future Work

- [ ] Real embedding model (sentence-transformers)
- [ ] Consolidation pipeline
- [ ] MCP server for Claude CLI
- [ ] Automatic Cascade context injection
- [ ] Web UI for browsing memory
- [ ] Cross-project entity linking

## License

MIT
