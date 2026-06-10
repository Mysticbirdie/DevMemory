# DevMemory — Universal Memory for AI Coding Tools

Cross-Tool Memory System. Extracts and unifies your AI coding conversations from **any IDE or CLI** into a searchable, persistent memory layer.

**Works with**: Devin, Cursor, VS Code + Copilot, Aider, Claude CLI, Claude Web, Git

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

| Source | What | How | Status |
|--------|------|-----|--------|
| **Devin** | Chat history, tool calls, file edits | VS Code extension SQLite DB | ✅ Ready |
| **Cursor** | AI chat, composer sessions | VS Code fork data files | ✅ Ready |
| **VS Code + Copilot** | GitHub Copilot Chat | Extension globalStorage | ✅ Ready |
| **Aider** | Pair programming sessions | CLI history files (`~/.aider/`) | ✅ Ready |
| **Claude CLI** | Conversations, project memory | Reads `~/.claude/` files | ✅ Ready |
| **Claude Web** | Exported chat JSON from claude.ai | Parses export files | ✅ Ready |
| **Git** | Commits, file changes, diffs | `git log` with stats | ✅ Ready |

## What It Produces

- **Sessions** — unified conversation history from all tools
- **Entities** — extracted concepts (e.g. Redis, FastAPI, your project names, etc.)
- **Decisions** — architectural choices with context
- **Patterns** — fixes, refactors, conventions discovered
- **File Activity** — what was touched when
- **Entity Graph** — relationships between concepts

## Architecture

```
┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐
│ Devin  │ │ Cursor │ │ VS Code  │ │ Aider  │ │ Claude   │ │  Git   │
│        │ │        │ │ Copilot  │ │        │ │ CLI/Web  │ │        │
└───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └────┬─────┘ └───┬────┘
    │          │           │           │           │           │
    └──────────┼───────────┼───────────┼───────────┼───────────┘
               │           │           │
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
| `extract --all` | Pull from **all** IDEs and tools |
| `extract --devin-local` | Extract from Devin |
| `extract --cursor` | Extract from Cursor IDE |
| `extract --vscode-copilot` | Extract from VS Code + Copilot |
| `extract --aider` | Extract from Aider CLI |
| `extract --claude` | Extract from Claude CLI |
| `extract --git` | Extract from Git |
| `search <query>` | Full-text search across all tools |
| `recent --days N` | Recent sessions |
| `entities` | Show extracted concepts |
| `decisions` | Show active decisions |
| `stats` | Database statistics |
| `related <entity>` | Entity relationship graph |
| `sync [--dry-run]` | Sync to Memory Banks |
| `import-web [--file]` | Import Claude Web exports |

## Project Brains

DevMemory can host canonical project memory for specific repositories. Each project gets:

- `project-map.md` — architecture, stack, modules
- `decision-log.md` — why things are the way they are
- `open-threads.md` — unresolved issues and risks
- `release/` — release briefs with scope and acceptance criteria
- `docs-index.json` — indexed docs with freshness tags
- `repo-facts.json` — machine-readable repo stats
- `prompts/` — reusable agent prompts for planning

Project brains live in `projects/<name>/` and are **gitignored by default** — they contain private decisions, risks, and release plans that should never be committed to a public repo. Store them locally or in a private repo.

**To use a project brain:**

```bash
# Read full context
cat projects/my-project/project-map.md
cat projects/my-project/open-threads.md

# Run planning prompts
cat projects/my-project/prompts/01-inventory-pass.md
```

**To create a new project brain:**
```bash
mkdir -p projects/<name>/{release,prompts}
# Create project-map.md, decision-log.md, open-threads.md
# See docs/CLAUDE_DESKTOP_MCP.md for full template and MCP setup
```

---

## Claude Web Integration

Bridge your Claude.ai web sessions into DevMemory. Works with any IDE:

```bash
# Export a chat from claude.ai (3-dot menu → Export chat)
# Then import into DevMemory:
python3 cli.py import-web --file ~/Downloads/chat_export.json

# Or scan ~/Downloads for all exports:
python3 cli.py import-web --all
```

**What gets preserved:**
- Full conversation turns (user + assistant)
- Entities extracted from the discussion
- Decisions made during the session
- Patterns discovered
- Cross-links with all IDE sessions

After import, sync to your IDE's memory banks:
```bash
python3 cli.py sync
```

## Memory Bank Bridge

Auto-populate your IDE's memory banks from DevMemory (works with any IDE that uses `.claude/memory/` or `.cascade/memory/`):

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

## Adding New IDE Support

DevMemory is designed to be extensible. Adding a new IDE takes ~30 minutes:

### 1. Create an Extractor

```python
# memory/extractors/my_ide.py
from .base import BaseExtractor

class MyIDEExtractor(BaseExtractor):
    TOOL_NAME = "my_ide"
    DISPLAY_NAME = "My IDE"
    
    def is_available(self) -> bool:
        # Check if IDE data exists
        return Path.home().exists()
    
    def extract(self, limit=None):
        # Return list of session dicts
        sessions = []
        # ... your extraction logic ...
        return sessions
```

### 2. Register in `__init__.py`

```python
from .my_ide import MyIDEExtractor
__all__ = [..., "MyIDEExtractor"]
```

### 3. Add CLI Flag

```python
extract_parser.add_argument("--my-ide", action="store_true", help="Extract from My IDE")
```

### 4. Add to `cmd_extract()`

```python
if args.my_ide or args.all:
    my_ide = MyIDEExtractor()
    if my_ide.is_available():
        sessions = my_ide.extract(limit=args.limit)
        total_sessions += _ingest_sessions(conn, sessions, extractor, summarizer)
```

That's it! The new IDE is now fully integrated with search, sync, and memory banks.

## Devin Local Integration

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

- [ ] **Zed IDE support** — Native AI chat integration
- [ ] **JetBrains IDEs** — IntelliJ, PyCharm, WebStorm AI assistants
- [ ] **Codeium support** — Free AI autocomplete and chat
- [ ] **Supermaven support** — AI code completion history
- [ ] **Continue.dev support** — Open-source AI assistant
- [ ] Real embedding model (sentence-transformers)
- [ ] Consolidation pipeline
- [ ] MCP server for Claude CLI
- [ ] Automatic context injection for any IDE
- [ ] Web UI for browsing memory
- [ ] Cross-project entity linking

## License

MIT
