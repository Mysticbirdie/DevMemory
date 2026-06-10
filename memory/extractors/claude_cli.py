"""Extractor for Claude CLI conversation history.

Reads from Claude Code's internal storage directories.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class ClaudeCLIExtractor(BaseExtractor):
    """Extracts conversation history from Claude CLI."""
    
    TOOL_NAME = "claude_cli"
    DISPLAY_NAME = "Claude CLI"
    
    # Claude Code stores data here
    CLAUDE_DIR = Path.home() / ".claude"
    CLAUDE_CACHE = Path.home() / ".claude" / "cache"
    
    def __init__(self, claude_dir: Optional[Path] = None):
        self.claude_dir = claude_dir or self.CLAUDE_DIR
        self.sessions: List[Dict] = []
    
    def is_available(self) -> bool:
        """Check if Claude CLI data is accessible."""
        return self.claude_dir.exists()
    
    def get_stats(self) -> Dict:
        """Return statistics about available Claude CLI data."""
        stats = super().get_stats()
        
        # Count conversation files
        conv_count = 0
        conv_dir = self.claude_dir / "conversations"
        if conv_dir.exists():
            conv_count = len(list(conv_dir.glob("*.json")))
        
        # Count memory files
        memory_count = 0
        memory_dir = self.claude_dir / "memory"
        if memory_dir.exists():
            memory_count = len(list(memory_dir.glob("*.md")))
        
        stats["conversation_files"] = conv_count
        stats["memory_files"] = memory_count
        stats["cache_exists"] = self.CLAUDE_CACHE.exists()
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        """Extract sessions from Claude CLI data sources.
        
        Args:
            limit: Max sessions to extract
            dry_run: If True, return preview stats without full session data
            
        Returns list of session dicts with format:
        {
            "tool": "claude_cli",
            "session_id": str,
            "started_at": str,
            "ended_at": str,
            "summary": str,
            "tags": list,
            "raw_content": str,
            "turns": [
                {
                    "role": "user" | "assistant" | "tool",
                    "content": str,
                    "timestamp": str,
                    "tool_calls": list (optional)
                }
            ]
        }
        """
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {stats.get('conversation_files', 0)} conversations, {stats.get('memory_files', 0)} memory files",
                "tags": ["dry-run"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        # Try to find conversation files
        if self.claude_dir.exists():
            try:
                # Look for conversation history files
                sessions.extend(self._extract_from_conversations(limit))
            except Exception as e:
                print(f"  Warning: Could not read Claude conversations: {e}")
            
            try:
                # Look for project memory files
                sessions.extend(self._extract_from_project_memory(limit))
            except Exception as e:
                print(f"  Warning: Could not read Claude memory files: {e}")
        
        # Validate and filter
        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)
    
    def _extract_from_conversations(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract from Claude's conversation storage."""
        sessions = []
        
        # Look for conversation JSON files
        conv_dir = self.claude_dir / "conversations"
        if not conv_dir.exists():
            conv_dir = self.claude_dir
        
        json_files = list(conv_dir.glob("*.json")) if conv_dir.exists() else []
        
        # Also check cache directory
        if self.CLAUDE_CACHE.exists():
            json_files.extend(self.CLAUDE_CACHE.glob("*.json"))
        
        for json_file in sorted(json_files, key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(json_file.read_text())
                session = self._parse_conversation_file(data, json_file.name)
                if session:
                    sessions.append(session)
            except (json.JSONDecodeError, Exception):
                continue
        
        return sessions
    
    def _extract_from_project_memory(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract from Claude's project memory files."""
        sessions = []
        
        # Read memory files that Claude CLI auto-updates
        memory_files = [
            self.claude_dir / "memory" / "activeContext.md",
            self.claude_dir / "memory" / "progress.md",
            self.claude_dir / "memory" / "sessionHistory.md",
        ]
        
        for mem_file in memory_files:
            if mem_file.exists():
                try:
                    content = mem_file.read_text()
                    session = self._parse_memory_file(content, mem_file.name)
                    if session:
                        sessions.append(session)
                except Exception:
                    continue
        
        return sessions
    
    def _parse_conversation_file(self, data: dict, filename: str) -> Optional[Dict]:
        """Parse a Claude conversation JSON file."""
        turns = []
        
        # Handle different possible structures
        if isinstance(data, dict):
            # Single conversation object
            messages = data.get('messages', []) or data.get('conversation', []) or []
            for msg in messages:
                if isinstance(msg, dict):
                    turns.append(self._parse_message(msg))
            
            session_id = data.get('id') or data.get('conversation_id') or filename
            started_at = data.get('started_at') or data.get('created_at')
            ended_at = data.get('ended_at') or data.get('last_message_at')
        
        elif isinstance(data, list):
            # Array of messages
            for msg in data:
                if isinstance(msg, dict):
                    turns.append(self._parse_message(msg))
            
            session_id = filename
            started_at = turns[0].get("timestamp") if turns else None
            ended_at = turns[-1].get("timestamp") if turns else None
        
        if not turns:
            return None
        
        return {
            "tool": "claude_cli",
            "session_id": f"claude_{session_id}",
            "started_at": started_at or turns[0].get("timestamp"),
            "ended_at": ended_at or turns[-1].get("timestamp"),
            "summary": self._generate_summary(turns),
            "tags": self._extract_tags(turns),
            "raw_content": json.dumps(turns),
            "turns": turns
        }
    
    def _parse_message(self, msg: dict) -> Dict:
        """Parse a single message dict."""
        return {
            "role": msg.get('role') or msg.get('sender') or 'unknown',
            "content": msg.get('content') or msg.get('text') or msg.get('message') or '',
            "timestamp": msg.get('timestamp') or msg.get('created_at') or datetime.now().isoformat(),
            "tool_calls": msg.get('tool_calls') or msg.get('tool_use')
        }
    
    def _parse_memory_file(self, content: str, filename: str) -> Optional[Dict]:
        """Parse a memory markdown file into a session structure."""
        # Memory files are markdown, not conversations
        # We'll create a synthetic session from the content
        
        return {
            "tool": "claude_cli",
            "session_id": f"claude_memory_{filename}",
            "started_at": datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "summary": f"Claude memory: {filename}",
            "tags": self._extract_tags_from_text(content),
            "raw_content": content,
            "turns": [
                {
                    "role": "system",
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
    
    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate a one-line summary from conversation turns."""
        user_messages = [t["content"] for t in turns if t.get("role") == "user"]
        if user_messages:
            first_msg = user_messages[0]
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "Claude CLI session"
    
    def _extract_tags(self, turns: List[Dict]) -> List[str]:
        """Extract tags from conversation content."""
        all_text = " ".join(t["content"] for t in turns if t.get("content"))
        return self._extract_tags_from_text(all_text)
    
    def _extract_tags_from_text(self, text: str) -> List[str]:
        """Extract tags from text."""
        tech_patterns = [
            r'\b(Stella|Triad|Redis|Firebase|PostgreSQL|Supabase)\b',
            r'\b(React|TypeScript|Python|FastAPI|Docker)\b',
            r'\b(bug|fix|debug|error|issue|refactor)\b',
            r'\b(feature|implement|add|create)\b',
        ]
        
        tags = set()
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            tags.update(m.lower() for m in matches)
        
        return list(tags)[:10]
