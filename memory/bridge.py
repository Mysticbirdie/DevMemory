"""Bridge DevMemory to Devin Local Memory Banks.

Syncs extracted decisions, patterns, and progress to .claude/memory/ and .cascade/memory/ files.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from .db import DB_PATH


MEMORY_PATHS = {
    "decisions": Path.home() / ".cascade" / "memory" / "decisions.md",
    "patterns": Path.home() / ".cascade" / "memory" / "patterns.md",
    "progress": Path.home() / ".claude" / "memory" / "progress.md",
    "active_context": Path.home() / ".claude" / "memory" / "activeContext.md",
}


def sync_decisions_to_memory_bank(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Sync new decisions from DevMemory to decisions.md.
    
    Args:
        conn: Database connection
        dry_run: If True, only report what would be added
        
    Returns:
        Number of decisions synced
    """
    cursor = conn.execute("""
        SELECT title, context, decision, rationale, decided_at
        FROM decisions
        WHERE status = 'active'
        AND decided_at > datetime('now', '-7 days')
        ORDER BY decided_at DESC
    """)
    
    recent_decisions = cursor.fetchall()
    if not recent_decisions:
        return 0
    
    decisions_file = MEMORY_PATHS["decisions"]
    existing_content = ""
    if decisions_file.exists():
        existing_content = decisions_file.read_text()
    
    synced = 0
    new_entries = []
    
    for row in recent_decisions:
        title, context, decision, rationale, decided_at = row
        # Check if already in file (simple title match)
        if title and title not in existing_content:
            entry = f"""\n### {decided_at[:10] if decided_at else datetime.now().strftime('%Y-%m-%d')}: {title}
**Context:** {context or 'From session analysis'}\n
**Decision:** {decision or title}\n
**Rationale:** {rationale or 'Extracted from development session'}\n
"""
            new_entries.append(entry)
            synced += 1
    
    if new_entries and not dry_run:
        # Ensure file has header
        if not existing_content.startswith("# Architectural Decisions"):
            existing_content = """# Architectural Decisions
**Auto-synced from DevMemory**\n
""" + existing_content
        
        existing_content += "\n".join(new_entries)
        decisions_file.parent.mkdir(parents=True, exist_ok=True)
        decisions_file.write_text(existing_content)
        print(f"📋 Synced {synced} decisions to {decisions_file}")
    elif new_entries and dry_run:
        print(f"Would sync {synced} decisions:")
        for entry in new_entries[:3]:
            print(f"  - {entry.split(chr(10))[0][:60]}...")
    
    return synced


def sync_patterns_to_memory_bank(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Sync discovered patterns to patterns.md.
    
    Args:
        conn: Database connection
        dry_run: If True, only report what would be added
        
    Returns:
        Number of patterns synced
    """
    cursor = conn.execute("""
        SELECT pattern_type, description, code_example, created_at
        FROM patterns
        WHERE created_at > datetime('now', '-7 days')
        ORDER BY created_at DESC
    """)
    
    recent_patterns = cursor.fetchall()
    if not recent_patterns:
        return 0
    
    patterns_file = MEMORY_PATHS["patterns"]
    existing_content = ""
    if patterns_file.exists():
        existing_content = patterns_file.read_text()
    
    synced = 0
    new_entries = []
    
    for row in recent_patterns:
        pattern_type, description, code_example, created_at = row
        # Check if already in file
        if description and description not in existing_content:
            entry = f"""\n### {pattern_type or 'Pattern'} ({created_at[:10] if created_at else 'recent'})
{description}\n
"""
            if code_example:
                entry += f"```\n{code_example}\n```\n\n"
            
            new_entries.append(entry)
            synced += 1
    
    if new_entries and not dry_run:
        if not existing_content.startswith("# Learned Patterns"):
            existing_content = """# Learned Patterns & Conventions
**Auto-synced from DevMemory**\n
""" + existing_content
        
        existing_content += "\n".join(new_entries)
        patterns_file.parent.mkdir(parents=True, exist_ok=True)
        patterns_file.write_text(existing_content)
        print(f"🔧 Synced {synced} patterns to {patterns_file}")
    elif new_entries and dry_run:
        print(f"Would sync {synced} patterns")
    
    return synced


def sync_progress_from_sessions(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Update progress.md with completed sessions.
    
    Args:
        conn: Database connection
        dry_run: If True, only report what would be updated
        
    Returns:
        Number of progress entries added
    """
    cursor = conn.execute("""
        SELECT summary, tags, started_at
        FROM sessions
        WHERE summary IS NOT NULL
        AND created_at > datetime('now', '-3 days')
        ORDER BY started_at DESC
    """)
    
    recent_sessions = cursor.fetchall()
    if not recent_sessions:
        return 0
    
    progress_file = MEMORY_PATHS["progress"]
    existing_content = ""
    if progress_file.exists():
        existing_content = progress_file.read_text()
    
    synced = 0
    new_entries = []
    
    for row in recent_sessions:
        summary, tags, started_at = row
        # Extract task name from summary
        if summary:
            task_line = summary.split('\n')[0][:50]
            entry = f"| {task_line} | 100% | Extracted |\n"
            
            if task_line not in existing_content:
                new_entries.append(entry)
                synced += 1
    
    if new_entries and not dry_run:
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Build or update table
        if "## Completed" not in existing_content:
            existing_content += "\n## Completed\n| Task | Progress | Source |\n|------|----------|--------|\n"
        
        existing_content += "\n".join(new_entries)
        progress_file.write_text(existing_content)
        print(f"✅ Synced {synced} progress entries to {progress_file}")
    elif new_entries and dry_run:
        print(f"Would sync {synced} progress entries")
    
    return synced


def sync_all(dry_run: bool = False) -> Dict[str, int]:
    """Run all sync operations.
    
    Args:
        dry_run: If True, only report what would be changed
        
    Returns:
        Dict with counts per category
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    results = {
        "decisions": sync_decisions_to_memory_bank(conn, dry_run),
        "patterns": sync_patterns_to_memory_bank(conn, dry_run),
        "progress": sync_progress_from_sessions(conn, dry_run),
    }
    
    conn.close()
    
    if not dry_run and any(results.values()):
        print(f"\n🔄 Memory Bank Bridge complete: {sum(results.values())} items synced")
    
    return results


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    sync_all(dry_run=dry)
