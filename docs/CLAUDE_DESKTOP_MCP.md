# Using DevMemory with Claude Desktop (MCP Filesystem)

Claude Desktop (the macOS/Windows app) supports local **MCP servers**, which means it can
read files on your machine — unlike Claude Web (claude.ai), which is browser-sandboxed.
This guide shows how to connect your DevMemory project brain directly to Claude Desktop.

---

## Why This Matters

| Surface | Local Files | DevMemory DB | Workaround |
|---------|-------------|--------------|------------|
| Claude Web (claude.ai) | ❌ | ❌ | Paste markdown manually |
| Claude Desktop App | ✅ via MCP | ✅ via MCP | Set up once, works forever |
| Claude CLI (`claude`) | ✅ | ✅ via CLI | Run `python3 cli.py sync` |
| Cascade/Windsurf | ✅ | ✅ | Reads `.cascade/memory/` |
| Devin Local | ✅ | ✅ | Reads `.windsurf/memory/` |

---

## Quick Setup (Claude Desktop)

### 1. Create your project brain

```bash
mkdir -p ~/CascadeProjects/DevMemory/projects/my-project
# Or use the DevMemory CLI to initialize
python3 cli.py init my-project
```

### 2. Edit `claude_desktop_config.json`

**Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add an `mcpServers` key:

```json
{
  "mcpServers": {
    "devmemory-brain": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/YOU/CascadeProjects/DevMemory/projects"
      ]
    }
  }
}
```

Replace `/Users/YOU/CascadeProjects/DevMemory/projects` with the actual path.

### 3. Restart Claude Desktop

The MCP server starts when Claude Desktop launches. After restart, Claude can
`read_file` and `list_directory` on your project brain.

### 4. Verify in Claude Desktop

Ask Claude: *"List the files in my project brain."*

It should respond with files from your `projects/` folder.

---

## Starter Prompt for Claude Desktop

Once MCP is connected, paste this to orient Claude to your project:

```
Read projects/my-project/project-map.md and projects/my-project/open-threads.md.
Then tell me: what is the current architecture, and what are the top 3 unresolved issues?
```

---

## Keep `projects/` Private

Your project brain contains private decisions, risks, and beta plans.
If you use the public DevMemory repo, make sure `projects/` is in `.gitignore`:

```
# Personal project brains — never commit
projects/
```

Store your project brain in a **private repo** or **local-only** folder,
and only point MCP at that path.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| MCP server doesn't start | Make sure `npx` and Node 18+ are on your PATH |
| Claude says "no tools available" | Restart the Desktop app after editing config |
| Permission denied | The path in `args` must be readable by the current user |
| `projects/` showing in `git status` | Add `projects/` to `.gitignore` |
