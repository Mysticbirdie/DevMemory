#!/usr/bin/env python3
"""CLI for Cross-Tool Memory System."""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

from memory.db import init_db, insert_session, search_sessions, get_recent_sessions
from memory.db import get_entities, get_active_decisions, get_stats
from memory.db import (
    insert_entity, insert_decision, insert_pattern,
    insert_file_activity, insert_entity_links,
)
from memory.extractors import CascadeExtractor, ClaudeCLIExtractor, GitExtractor
from memory.intelligence import EntityExtractor, SessionSummarizer


def cmd_init(args):
    """Initialize the database."""
    conn = init_db()
    print("✅ Database initialized at ~/.dev-memory/memory.db")
    conn.close()


def _ingest_sessions(conn, sessions, extractor, summarizer) -> int:
    """Run intelligence over sessions and persist everything to the DB.

    Persists: session + turns, entities, decisions, patterns, entity
    co-occurrence links, and file activity. (Shared by all extractors.)
    """
    count = 0
    for session in sessions:
        intel = extractor.extract_from_session(session)
        session["tags"] = intel["tags"]
        session["summary"] = summarizer.summarize(session)

        session_id = insert_session(conn, session)
        count += 1

        for entity in intel["entities"]:
            insert_entity(conn, entity["name"], entity["type"], entity.get("context", ""))

        for decision in intel["decisions"]:
            decision["session_id"] = session_id
            insert_decision(conn, decision)

        for pattern in intel["patterns"]:
            insert_pattern(conn, {
                "session_id": session_id,
                "pattern_type": pattern.get("type"),          # extractor uses "type"
                "description": pattern.get("description"),
                "code_example": pattern.get("code_example"),
                "related_files": pattern.get("related_files", []),
            })

        for fpath in intel["files"]:
            insert_file_activity(conn, session_id, fpath)

        # Build the entity co-occurrence graph (powers `related`)
        insert_entity_links(conn, intel["entities"])

    return count


def cmd_extract(args):
    """Extract and store data from tools."""
    conn = init_db()
    extractor = EntityExtractor()
    summarizer = SessionSummarizer()
    total_sessions = 0

    if args.cascade or args.all:
        print("Extracting from Cascade/Windsurf...")
        cascade = CascadeExtractor()
        if cascade.is_available():
            sessions = cascade.extract(limit=args.limit)
            total_sessions += _ingest_sessions(conn, sessions, extractor, summarizer)
            print(f"  📥 {len(sessions)} Cascade sessions")
        else:
            print("  ⚠️ Cascade data not found")

    if args.claude or args.all:
        print("Extracting from Claude CLI...")
        claude = ClaudeCLIExtractor()
        if claude.is_available():
            sessions = claude.extract(limit=args.limit)
            total_sessions += _ingest_sessions(conn, sessions, extractor, summarizer)
            print(f"  📥 {len(sessions)} Claude CLI sessions")
        else:
            print("  ⚠️ Claude CLI data not found")

    if args.git or args.all:
        print("Extracting from Git...")
        git = GitExtractor()
        if git.is_available():
            since_str = f"{args.since} days ago" if args.since else "30 days ago"
            sessions = git.extract(limit=args.limit, since=since_str)
            total_sessions += _ingest_sessions(conn, sessions, extractor, summarizer)
            print(f"  📥 {len(sessions)} Git commits")
        else:
            print("  ⚠️ Git data not found")

    conn.close()
    print(f"\n✅ Total sessions stored: {total_sessions}")


def cmd_search(args):
    """Search across all sessions."""
    conn = init_db()
    results = search_sessions(conn, args.query, limit=args.limit)
    
    if not results:
        print("No results found.")
        conn.close()
        return
    
    print(f"\n🔍 Found {len(results)} results for: '{args.query}'\n")
    
    for r in results:
        tool_emoji = {"cascade": "⚡", "claude_cli": "🧠", "git": "📦"}.get(r.get("tool"), "📝")
        date = r.get("started_at", "unknown")[:10] if r.get("started_at") else "unknown"
        summary = r.get("summary", "No summary")[:80]
        
        print(f"{tool_emoji} [{date}] {summary}")
        print(f"   Tool: {r.get('tool', 'unknown')} | Session: {r.get('session_id', 'unknown')[:8]}")
        print()
    
    conn.close()


def cmd_recent(args):
    """Show recent sessions."""
    conn = init_db()
    sessions = get_recent_sessions(conn, days=args.days, tool=args.tool)
    
    if not sessions:
        print("No recent sessions found.")
        conn.close()
        return
    
    print(f"\n📅 Last {args.days} days ({len(sessions)} sessions)\n")
    
    for s in sessions:
        tool_emoji = {"cascade": "⚡", "claude_cli": "🧠", "git": "📦"}.get(s.get("tool"), "📝")
        date = s.get("started_at", "")[:16] if s.get("started_at") else "unknown"
        summary = s.get("summary", "No summary")[:60]
        tags = s.get("tags", "")
        if tags:
            try:
                tags = json.loads(tags)
                tags_str = ", ".join(tags[:3])
            except:
                tags_str = str(tags)[:30]
        else:
            tags_str = ""
        
        print(f"{tool_emoji} {date} | {summary}")
        if tags_str:
            print(f"   🏷️ {tags_str}")
        print()
    
    conn.close()


def cmd_entities(args):
    """Show extracted entities."""
    conn = init_db()
    entities = get_entities(conn, entity_type=args.type, min_mentions=args.min)
    
    if not entities:
        print("No entities found.")
        conn.close()
        return
    
    print(f"\n🏷️ Entities ({len(entities)} found)\n")
    
    for e in entities[:args.limit]:
        name = e.get("name", "unknown")
        etype = e.get("type", "unknown")
        count = e.get("mention_count", 0)
        first = e.get("first_seen", "")[:10] if e.get("first_seen") else "?"
        
        print(f"  {name} ({etype}) - mentioned {count}x, first seen {first}")
    
    conn.close()


def cmd_decisions(args):
    """Show active decisions."""
    conn = init_db()
    decisions = get_active_decisions(conn)
    
    if not decisions:
        print("No active decisions found.")
        conn.close()
        return
    
    print(f"\n📋 Active Decisions ({len(decisions)})\n")
    
    for d in decisions[:args.limit]:
        title = d.get("title", "Untitled")[:80]
        date = d.get("decided_at", "")[:10] if d.get("decided_at") else "?"
        
        print(f"  [{date}] {title}")
        if d.get("rationale"):
            rationale = d["rationale"][:100]
            print(f"    Why: {rationale}")
        print()
    
    conn.close()


def cmd_stats(args):
    """Show database statistics."""
    conn = init_db()
    stats = get_stats(conn)
    
    print("\n📊 Memory Statistics\n")
    print(f"  Sessions: {stats.get('sessions', 0)}")
    print(f"  Turns: {stats.get('turns', 0)}")
    print(f"  Entities: {stats.get('entities', 0)}")
    print(f"  Decisions: {stats.get('decisions', 0)}")
    print(f"  Patterns: {stats.get('patterns', 0)}")
    print(f"  File Activities: {stats.get('file_activity', 0)}")
    
    if stats.get("tools"):
        print("\n  By Tool:")
        for tool, count in stats["tools"].items():
            print(f"    {tool}: {count}")
    
    conn.close()


def cmd_related(args):
    """Show entities related to a given entity."""
    conn = init_db()
    from memory.db import get_entity_graph
    
    graph = get_entity_graph(conn, args.entity, depth=args.depth)
    
    if not graph or not graph.get("entity"):
        print(f"Entity '{args.entity}' not found.")
        conn.close()
        return
    
    entity = graph["entity"]
    print(f"\n🔗 {entity['name']} ({entity.get('type', 'unknown')})\n")
    print(f"  Mentioned {entity.get('mention_count', 0)} times")
    print(f"  First seen: {entity.get('first_seen', '?')[:10]}")
    
    neighbors = graph.get("neighbors", [])
    if neighbors:
        print(f"\n  Related ({len(neighbors)}):")
        for n in neighbors[:args.limit]:
            print(f"    → {n['name']} ({n.get('type', 'unknown')}) - strength: {n.get('strength', 0):.2f}")
    else:
        print("\n  No related entities found yet.")
    
    conn.close()


def cmd_sync(args):
    """Sync DevMemory to Windsurf Memory Banks."""
    from memory.bridge import sync_all
    
    results = sync_all(dry_run=args.dry_run)
    
    if args.dry_run:
        print("\n🔍 Dry run - no changes made")
    else:
        total = sum(results.values())
        if total == 0:
            print("\n✅ Memory banks already up to date")
        else:
            print(f"\n✅ Synced {total} items to Memory Banks")


def cmd_import_web(args):
    """Import Claude Web exports."""
    from memory.extractors.claude_web import ClaudeWebExtractor
    
    extractor = ClaudeWebExtractor()
    
    if args.all:
        # Import all found exports
        sessions = extractor.extract()
    elif args.file:
        # Import specific file
        from pathlib import Path
        sessions = extractor.extract(specific_file=Path(args.file))
    else:
        # Just list available exports
        sessions = extractor.watch_and_import(auto_import=False)
        return
    
    if not sessions:
        print("No sessions to import.")
        return
    
    conn = init_db()
    from memory.db import insert_session, insert_entity, insert_decision
    from memory.intelligence import EntityExtractor, SessionSummarizer
    
    intel_extractor = EntityExtractor()
    summarizer = SessionSummarizer()
    
    total_imported = 0
    
    print(f"\n📥 Importing {len(sessions)} Claude Web session(s)...\n")
    
    for session in sessions:
        # Enhance with intelligence
        intel = intel_extractor.extract_from_session(session)
        session["tags"] = intel["tags"]
        session["summary"] = summarizer.summarize(session)
        
        session_id = insert_session(conn, session)
        total_imported += 1
        
        # Store entities
        for entity in intel["entities"]:
            insert_entity(conn, entity["name"], entity["type"], entity["context"])
        
        # Store decisions
        for decision in intel["decisions"]:
            decision["session_id"] = session_id
            insert_decision(conn, decision)
        
        print(f"  ✅ {session.get('summary', 'Untitled')[:60]}...")
    
    conn.close()
    print(f"\n✅ Total imported: {total_imported}")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Tool Memory - Universal memory for Cascade, Claude CLI, and Git"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    init_parser = subparsers.add_parser("init", help="Initialize the database")
    init_parser.set_defaults(func=cmd_init)
    
    # extract
    extract_parser = subparsers.add_parser("extract", help="Extract data from tools")
    extract_parser.add_argument("--all", action="store_true", help="Extract from all tools")
    extract_parser.add_argument("--cascade", action="store_true", help="Extract from Cascade/Windsurf")
    extract_parser.add_argument("--claude", action="store_true", help="Extract from Claude CLI")
    extract_parser.add_argument("--git", action="store_true", help="Extract from Git")
    extract_parser.add_argument("--limit", type=int, default=100, help="Max sessions to extract")
    extract_parser.add_argument("--since", type=int, default=30, help="Git: days ago to start from")
    extract_parser.set_defaults(func=cmd_extract)
    
    # search
    search_parser = subparsers.add_parser("search", help="Search across all sessions")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    search_parser.set_defaults(func=cmd_search)
    
    # recent
    recent_parser = subparsers.add_parser("recent", help="Show recent sessions")
    recent_parser.add_argument("--days", type=int, default=7, help="Number of days")
    recent_parser.add_argument("--tool", choices=["cascade", "claude_cli", "git"], help="Filter by tool")
    recent_parser.set_defaults(func=cmd_recent)
    
    # entities
    entities_parser = subparsers.add_parser("entities", help="Show extracted entities")
    entities_parser.add_argument("--type", help="Filter by type")
    entities_parser.add_argument("--min", type=int, default=1, help="Min mention count")
    entities_parser.add_argument("--limit", type=int, default=20, help="Max results")
    entities_parser.set_defaults(func=cmd_entities)
    
    # decisions
    decisions_parser = subparsers.add_parser("decisions", help="Show active decisions")
    decisions_parser.add_argument("--limit", type=int, default=20, help="Max results")
    decisions_parser.set_defaults(func=cmd_decisions)
    
    # stats
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync DevMemory to Windsurf Memory Banks")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without writing")
    sync_parser.set_defaults(func=cmd_sync)
    
    # related
    related_parser = subparsers.add_parser("related", help="Show related entities")
    related_parser.add_argument("entity", help="Entity name")
    related_parser.add_argument("--depth", type=int, default=1, help="Graph depth")
    related_parser.add_argument("--limit", type=int, default=10, help="Max results")
    related_parser.set_defaults(func=cmd_related)
    
    # import-web
    import_web_parser = subparsers.add_parser("import-web", help="Import Claude Web exports")
    import_web_parser.add_argument("--file", help="Specific export file to import")
    import_web_parser.add_argument("--all", action="store_true", help="Import all found exports")
    import_web_parser.set_defaults(func=cmd_import_web)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
