#!/bin/bash
# Unified DevMemory Extraction Script
# Extracts from ALL IDEs and tools, then syncs to memory banks
# Run before switching IDEs or after important sessions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧠 DevMemory Unified Extraction"
echo "================================"
echo ""

# Check if we're in the DevMemory repo
if [ ! -f "cli.py" ]; then
    echo "❌ Error: cli.py not found. Run from DevMemory repo root."
    exit 1
fi

# Initialize if needed
if [ ! -f "$HOME/.dev-memory/memory.db" ]; then
    echo "📦 Initializing DevMemory database..."
    python3 cli.py init
    echo ""
fi

# Extract from all IDEs and tools
echo "🔍 Extracting from all IDEs and tools..."
echo ""

# Devin (VS Code extension)
python3 cli.py extract --devin-local || echo "  ⚠️ Devin not available"

# Cursor (VS Code fork)
python3 cli.py extract --cursor || echo "  ⚠️ Cursor not available"

# VS Code + Copilot
python3 cli.py extract --vscode-copilot || echo "  ⚠️ VS Code Copilot not available"

# Aider (CLI pair programming)
python3 cli.py extract --aider || echo "  ⚠️ Aider not available"

# Claude CLI
python3 cli.py extract --claude || echo "  ⚠️ Claude CLI not available"

# Git
python3 cli.py extract --git || echo "  ⚠️ Git not available"

echo ""
echo "🔄 Syncing to Memory Banks..."
python3 cli.py sync

echo ""
echo "✅ Unified extraction complete!"
echo ""

# Show stats
echo "📊 Current Memory Stats:"
python3 cli.py stats

echo ""
echo "📝 Recent Activity:"
python3 cli.py recent --days 1 || true

echo ""
echo "🎯 Next steps:"
echo "  - All your IDE conversations are now in one place"
echo "  - Memory banks updated with latest decisions and patterns"
echo "  - Switch between IDEs without losing context"
