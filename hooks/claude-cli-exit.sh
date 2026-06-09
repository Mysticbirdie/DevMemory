#!/bin/bash
# Claude CLI Exit Hook - Auto-extract DevMemory on session end
# 
# Installation:
#   1. Set DEV_MEMORY_REPO (optional - auto-detected in common locations):
#      export DEV_MEMORY_REPO=/path/to/your/dev-memory
#   2. Add to ~/.bashrc or ~/.zshrc:
#      source $DEV_MEMORY_REPO/hooks/claude-cli-exit.sh
#   3. Use 'claude' wrapper function instead of direct claude command
#   4. Auto-extract runs after each /exit or session end
#
# Or manually run after Claude CLI:
#   claude-extract

# Configuration
DEV_MEMORY_DIR="${HOME}/.dev-memory"
CLAUDE_LOGS_DIR="${HOME}/.claude"
# Auto-detect dev-memory location: use DEV_MEMORY_REPO if set, else search common locations
if [ -z "$DEV_MEMORY_REPO" ]; then
    # Try to find dev-memory in common locations
    if [ -d "${HOME}/CascadeProjects/Birdhouse/dev-memory" ]; then
        DEV_MEMORY_REPO="${HOME}/CascadeProjects/Birdhouse/dev-memory"
    elif [ -d "${HOME}/projects/birdhouse/dev-memory" ]; then
        DEV_MEMORY_REPO="${HOME}/projects/birdhouse/dev-memory"
    elif [ -d "./dev-memory" ]; then
        DEV_MEMORY_REPO="$(pwd)/dev-memory"
    else
        DEV_MEMORY_REPO=""  # Will fallback to pip install or PATH
    fi
fi

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Main extract function
claude-extract() {
    echo -e "${BLUE}🔍 DevMemory: Extracting from Claude CLI...${NC}"
    
    # Check if dev-memory repo is available
    if [ -n "$DEV_MEMORY_REPO" ] && [ -f "${DEV_MEMORY_REPO}/cli.py" ]; then
        cd "$DEV_MEMORY_REPO"
        python3 -m memory.cli extract --tool claude-cli --days 1
        
        # Also sync to memory banks
        echo -e "${BLUE}🔄 Syncing to Memory Banks...${NC}"
        python3 -c "from memory.bridge import sync_all; sync_all()"
    else
        # Fallback: use global dev-memory if installed
        if command -v dev-memory &> /dev/null; then
            dev-memory extract --tool claude-cli --days 1
            dev-memory sync-banks
        else
            echo -e "${YELLOW}⚠️  DevMemory not found. Set DEV_MEMORY_REPO or install dev-memory.${NC}"
            echo -e "   Example: export DEV_MEMORY_REPO=/path/to/your/dev-memory"
        fi
    fi
    
    echo -e "${GREEN}✅ DevMemory extraction complete${NC}"
}

# Wrapper function for Claude CLI
claude() {
    # Run actual claude command with all arguments
    command claude "$@"
    CLAUDE_EXIT_CODE=$?
    
    # Check if this was an interactive session (not a one-off command)
    if [ $CLAUDE_EXIT_CODE -eq 0 ] && [ -z "$CLAUDE_NON_INTERACTIVE" ]; then
        # Only extract if session lasted more than 30 seconds (heuristic)
        # In practice, we extract on every exit
        echo -e "${BLUE}💾 Running post-session extraction...${NC}"
        claude-extract
    fi
    
    return $CLAUDE_EXIT_CODE
}

# Alias for quick extraction without full sync
claude-quick-extract() {
    echo -e "${BLUE}⚡ Quick extract (last session only)...${NC}"
    if [ -n "$DEV_MEMORY_REPO" ]; then
        cd "$DEV_MEMORY_REPO" 2>/dev/null || true
        python3 -m memory.cli extract --tool claude-cli --limit 1 --quiet 2>/dev/null || true
    else
        echo -e "${YELLOW}⚠️  DEV_MEMORY_REPO not set${NC}"
    fi
}

# Export functions for use in shell
export -f claude-extract 2>/dev/null || true
export -f claude 2>/dev/null || true
export -f claude-quick-extract 2>/dev/null || true

# If script is sourced, print setup message
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
    echo -e "${GREEN}✅ Claude CLI Hook loaded${NC}"
    echo -e "   Use ${YELLOW}claude${NC} for auto-extract on exit"
    echo -e "   Use ${YELLOW}claude-extract${NC} for manual extraction"
    echo -e "   Use ${YELLOW}claude-quick-extract${NC} for fast single-session capture"
fi
