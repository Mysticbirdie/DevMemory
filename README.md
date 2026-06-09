# Cross-Tool Memory System

Universal memory layer that sees everything you do across Cascade/Windsurf, Claude CLI, and Git.

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
| `sync [--dry-run]` | Sync to Windsurf Memory Banks |

## Windsurf Memory Bank Bridge

Auto-populate your memory banks from DevMemory:

```bash
# Sync decisions to .cascade/memory/decisions.md
python3 cli.py sync

# Preview without writing
python3 cli.py sync --dry-run
```

Syncs:
- **Decisions** → `.cascade/memory/decisions.md`
- **Patterns** → `.cascade/memory/patterns.md`
- **Progress** → `.claude/memory/progress.md`

## Claude CLI Hook

Auto-extract on every `/exit`:

```bash
# Add to ~/.bashrc or ~/.zshrc
source /path/to/dev-memory/hooks/claude-cli-exit.sh

# Now 'claude' wrapper auto-extracts on exit
claude
# ... work ...
/exit
# 💾 Auto-extract runs
```

Or manual extraction:
```bash
claude-extract        # Full extract + sync
claude-quick-extract  # Fast single-session
```

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
