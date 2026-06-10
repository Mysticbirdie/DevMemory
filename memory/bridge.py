"""Bridge DevMemory to Devin Local Memory Banks.

Syncs extracted decisions, patterns, and progress to .claude/memory/ and .cascade/memory/ files.

Reliability features:
- Backs up existing memory banks before writing
- Adds timestamps to prevent duplicate entries
- Creates per-tool memory bank files
- Handles merge conflict markers gracefully
"""

import sqlite3
import shutil
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


def _per_tool_path(base_dir: Path, tool: str, filename: str) -> Path:
    """Return path for a per-tool memory bank file."""
    tool_dir = base_dir / tool
    tool_dir.mkdir(parents=True, exist_ok=True)
    return tool_dir / filename


def _backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup of a memory bank file."""
    if not file_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".md.bak.{timestamp}")
    shutil.copy2(str(file_path), str(backup_path))
    return backup_path


def _has_merge_conflicts(content: str) -> bool:
    """Check if content contains Git merge conflict markers."""
    return any(marker in content for marker in ["<<<<<<<", "=======", ">>>>>>>"])


def _strip_merge_conflicts(content: str) -> str:
    """Remove merge conflict markers, keeping both versions for manual review."""
    lines = content.split('\n')
    clean_lines = []
    in_conflict = False
    for line in lines:
        if line.startswith("<<<<<<<"):
            in_conflict = True
            clean_lines.append("<!-- MERGE CONFLICT: both versions kept -->")
            continue
        if line.startswith("======="):
            continue
        if line.startswith(">>>>>>>"):
            in_conflict = False
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)


def _is_entry_synced(existing_content: str, entry_id: str) -> bool:
    """Check if an entry (by id/title) is already in the memory bank."""
    return entry_id in existing_content


def _insert_timestamped_entry(existing: str, entry: str) -> str:
    """Append entry with a sync timestamp comment."""
    ts = datetime.now().isoformat()
    return existing + f"\n<!-- synced: {ts} -->\n" + entry


def sync_decisions_to_memory_bank(conn: sqlite3.Connection, dry_run: bool = False, tool_filter: Optional[str] = None) -> int:
    """Sync new decisions from DevMemory to decisions.md.

    Args:
        conn: Database connection
        dry_run: If True, only report what would be added
        tool_filter: If set, only sync decisions from this tool

    Returns:
        Number of decisions synced
    """
    query = """
        SELECT d.title, d.context, d.decision, d.rationale, d.decided_at, s.tool
        FROM decisions d
        JOIN sessions s ON d.session_id = s.session_id
        WHERE d.status = 'active'
        AND d.decided_at > datetime('now', '-7 days')
    """
    params = []
    if tool_filter:
        query += " AND s.tool = ?"
        params.append(tool_filter)
    query += " ORDER BY d.decided_at DESC"

    cursor = conn.execute(query, params)
    recent_decisions = cursor.fetchall()
    if not recent_decisions:
        return 0

    decisions_file = MEMORY_PATHS["decisions"]
    existing_content = ""
    if decisions_file.exists():
        existing_content = decisions_file.read_text()
        if _has_merge_conflicts(existing_content):
            existing_content = _strip_merge_conflicts(existing_content)

    synced = 0
    new_entries = []

    for row in recent_decisions:
        title, context, decision, rationale, decided_at, tool = row
        entry_id = f"{decided_at[:10] if decided_at else 'unknown'}: {title}"
        if title and not _is_entry_synced(existing_content, entry_id):
            entry = f"""\n### {entry_id}
**Context:** {context or 'From session analysis'}\n
**Decision:** {decision or title}\n
**Rationale:** {rationale or 'Extracted from development session'}\n
**Source:** {tool}\n
"""
            new_entries.append(entry)
            synced += 1

    if new_entries and not dry_run:
        if not existing_content.startswith("# Architectural Decisions"):
            existing_content = """# Architectural Decisions
**Auto-synced from DevMemory**\n
""" + existing_content

        _backup_file(decisions_file)
        for entry in new_entries:
            existing_content = _insert_timestamped_entry(existing_content, entry)
        decisions_file.parent.mkdir(parents=True, exist_ok=True)
        decisions_file.write_text(existing_content)
        print(f"📋 Synced {synced} decisions to {decisions_file}")

        # Also write per-tool file
        if tool_filter:
            tool_path = _per_tool_path(Path.home() / ".cascade" / "memory", tool_filter, "decisions.md")
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            tool_path.write_text(existing_content)
    elif new_entries and dry_run:
        print(f"Would sync {synced} decisions:")
        for entry in new_entries[:3]:
            print(f"  - {entry.split(chr(10))[0][:60]}...")

    return synced


def sync_patterns_to_memory_bank(conn: sqlite3.Connection, dry_run: bool = False, tool_filter: Optional[str] = None) -> int:
    """Sync discovered patterns to patterns.md.

    Args:
        conn: Database connection
        dry_run: If True, only report what would be added
        tool_filter: If set, only sync patterns from this tool

    Returns:
        Number of patterns synced
    """
    query = """
        SELECT p.pattern_type, p.description, p.code_example, p.created_at, s.tool
        FROM patterns p
        JOIN sessions s ON p.session_id = s.session_id
        WHERE p.created_at > datetime('now', '-7 days')
    """
    params = []
    if tool_filter:
        query += " AND s.tool = ?"
        params.append(tool_filter)
    query += " ORDER BY p.created_at DESC"

    cursor = conn.execute(query, params)
    recent_patterns = cursor.fetchall()
    if not recent_patterns:
        return 0

    patterns_file = MEMORY_PATHS["patterns"]
    existing_content = ""
    if patterns_file.exists():
        existing_content = patterns_file.read_text()
        if _has_merge_conflicts(existing_content):
            existing_content = _strip_merge_conflicts(existing_content)

    synced = 0
    new_entries = []

    for row in recent_patterns:
        pattern_type, description, code_example, created_at, tool = row
        entry_id = f"{pattern_type or 'Pattern'}: {description[:50] if description else 'unknown'}"
        if description and not _is_entry_synced(existing_content, entry_id):
            entry = f"""\n### {pattern_type or 'Pattern'} ({created_at[:10] if created_at else 'recent'})
{description}\n
**Source:** {tool}\n
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

        _backup_file(patterns_file)
        for entry in new_entries:
            existing_content = _insert_timestamped_entry(existing_content, entry)
        patterns_file.parent.mkdir(parents=True, exist_ok=True)
        patterns_file.write_text(existing_content)
        print(f"🔧 Synced {synced} patterns to {patterns_file}")

        if tool_filter:
            tool_path = _per_tool_path(Path.home() / ".cascade" / "memory", tool_filter, "patterns.md")
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            tool_path.write_text(existing_content)
    elif new_entries and dry_run:
        print(f"Would sync {synced} patterns")

    return synced


def sync_progress_from_sessions(conn: sqlite3.Connection, dry_run: bool = False, tool_filter: Optional[str] = None) -> int:
    """Update progress.md with completed sessions.

    Args:
        conn: Database connection
        dry_run: If True, only report what would be updated
        tool_filter: If set, only sync sessions from this tool

    Returns:
        Number of progress entries added
    """
    query = """
        SELECT summary, tags, started_at, tool
        FROM sessions
        WHERE summary IS NOT NULL
        AND created_at > datetime('now', '-3 days')
    """
    params = []
    if tool_filter:
        query += " AND tool = ?"
        params.append(tool_filter)
    query += " ORDER BY started_at DESC"

    cursor = conn.execute(query, params)
    recent_sessions = cursor.fetchall()
    if not recent_sessions:
        return 0

    progress_file = MEMORY_PATHS["progress"]
    existing_content = ""
    if progress_file.exists():
        existing_content = progress_file.read_text()
        if _has_merge_conflicts(existing_content):
            existing_content = _strip_merge_conflicts(existing_content)

    synced = 0
    new_entries = []

    for row in recent_sessions:
        summary, tags, started_at, tool = row
        if summary:
            task_line = summary.split('\n')[0][:50]
            entry = f"| {task_line} | 100% | {tool} |\n"

            if task_line not in existing_content:
                new_entries.append(entry)
                synced += 1

    if new_entries and not dry_run:
        progress_file.parent.mkdir(parents=True, exist_ok=True)

        if "## Completed" not in existing_content:
            existing_content += "\n## Completed\n| Task | Progress | Source |\n|------|----------|--------|\n"

        _backup_file(progress_file)
        for entry in new_entries:
            existing_content = _insert_timestamped_entry(existing_content, entry)
        progress_file.write_text(existing_content)
        print(f"✅ Synced {synced} progress entries to {progress_file}")

        if tool_filter:
            tool_path = _per_tool_path(Path.home() / ".claude" / "memory", tool_filter, "progress.md")
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            tool_path.write_text(existing_content)
    elif new_entries and dry_run:
        print(f"Would sync {synced} progress entries")

    return synced


def sync_all(dry_run: bool = False, tool_filter: Optional[str] = None) -> Dict[str, int]:
    """Run all sync operations.

    Args:
        dry_run: If True, only report what would be changed
        tool_filter: If set, only sync entries from this tool

    Returns:
        Dict with counts per category
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    results = {
        "decisions": sync_decisions_to_memory_bank(conn, dry_run, tool_filter),
        "patterns": sync_patterns_to_memory_bank(conn, dry_run, tool_filter),
        "progress": sync_progress_from_sessions(conn, dry_run, tool_filter),
    }

    conn.close()

    if not dry_run and any(results.values()):
        print(f"\n🔄 Memory Bank Bridge complete: {sum(results.values())} items synced")

    return results


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    sync_all(dry_run=dry)
