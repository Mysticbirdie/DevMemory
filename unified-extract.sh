#!/bin/bash
# Unified DevMemory Extraction Script
# Extracts from ALL tools (Devin Local, Claude CLI, Git) and syncs to memory banks
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

# Extract from all tools
echo "🔍 Extracting from all tools..."
echo ""

# Devin Local (current IDE)
python3 cli.py extract --devin-local || echo "  ⚠️ Devin Local not available"

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
echo "  - Devin Local will now have access to all extracted conversations"
echo "  - Memory banks updated with latest decisions and patterns"
echo "  - Claude CLI history preserved for future reference"
