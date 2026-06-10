"""Extractor for Cursor IDE chat history.

Cursor is a VS Code fork with AI chat features.
Reads from Cursor's internal data storage.
"""

import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class CursorExtractor(BaseExtractor):
    """Extracts conversation history from Cursor IDE."""
    
    TOOL_NAME = "cursor"
    DISPLAY_NAME = "Cursor IDE"
    
    # Primary database locations by platform
    DATA_DIRS = {
        "darwin": Path.home() / "Library" / "Application Support" / "Cursor",
        "linux": Path.home() / ".config" / "Cursor",
        "win32": Path.home() / "AppData" / "Roaming" / "Cursor",
    }
    
    def __init__(self, db_path: Optional[Path] = None):
        import sys
        self.platform = sys.platform
        self.data_dir = db_path or self.DATA_DIRS.get(self.platform)
        self.sessions: List[Dict] = []
    
    def is_available(self) -> bool:
        """Check if Cursor data is accessible."""
        return self.data_dir and self.data_dir.exists()
    
    def get_stats(self) -> Dict:
        """Return statistics about available Cursor data."""
        stats = super().get_stats()
        stats["data_dir"] = str(self.data_dir) if self.data_dir else None
        stats["platform"] = self.platform
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        """Extract sessions from Cursor data sources."""
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: Cursor data dir exists at {stats.get('data_dir', 'unknown')}",
                "tags": ["dry-run"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        # Try multiple data sources
        try:
            sessions.extend(self._extract_from_sqlite(limit))
        except Exception as e:
            print(f"  Warning: Could not read Cursor SQLite: {e}")
        
        try:
            sessions.extend(self._extract_from_json_logs(limit))
        except Exception as e:
            print(f"  Warning: Could not read Cursor JSON logs: {e}")
        
        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)
    
    def _extract_from_sqlite(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract from Cursor's SQLite database (if present).
        
        Cursor stores chat history in a SQLite DB similar to VS Code.
        """
        sessions = []
        
        # Cursor may store data in various locations
        possible_db_paths = [
            self.data_dir / "User" / "globalStorage" / "state.vscdb",
            self.data_dir / "User" / "globalStorage" / "state.sqlite",
            self.data_dir / "state.vscdb",
        ]
        
        db_path = None
        for path in possible_db_paths:
            if path.exists():
                db_path = path
                break
        
        if not db_path:
            return sessions
        
        # Copy database to avoid locking
        temp_db = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
                temp_db = tmp.name
            shutil.copy2(str(db_path), temp_db)
            
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # Look for chat/conversation tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            
            # Common table names for chat history
            chat_tables = [t for t in tables if 'chat' in t.lower() or 'conversation' in t.lower()]
            
            for table in chat_tables[:3]:  # Limit to first 3 chat tables
                try:
                    cursor.execute(f"SELECT * FROM {table} LIMIT ?", [limit or 1000])
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        # Attempt to parse chat data
                        session = self._parse_chat_row(row, table)
                        if session:
                            sessions.append(session)
                            
                except Exception:
                    continue
            
            conn.close()
            
        finally:
            if temp_db and Path(temp_db).exists():
                Path(temp_db).unlink()
        
        return sessions
    
    def _extract_from_json_logs(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract from Cursor's JSON log files.
        
        Cursor may store chat history as JSON files.
        """
        sessions = []
        
        # Look for JSON log files
        log_dirs = [
            self.data_dir / "logs",
            self.data_dir / "User" / "globalStorage",
        ]
        
        for log_dir in log_dirs:
            if not log_dir.exists():
                continue
            
            for json_file in log_dir.glob("**/*.json"):
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    # Check if this looks like chat data
                    if isinstance(data, list) and len(data) > 0:
                        session = self._parse_json_chat(data, json_file.name)
                        if session:
                            sessions.append(session)
                            
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        
        return sessions[:limit] if limit else sessions
    
    def _parse_chat_row(self, row: tuple, table_name: str) -> Optional[Dict]:
        """Parse a database row into a session dict."""
        # This is a generic parser - actual schema may vary
        try:
            # Try to extract content from the row
            content = None
            timestamp = datetime.now().isoformat()
            
            # Look for common column patterns
            for item in row:
                if isinstance(item, str) and len(item) > 50:
                    content = item
                    break
            
            if not content:
                return None
            
            return {
                "tool": self.TOOL_NAME,
                "session_id": f"cursor_{table_name}_{hash(content) % 10000}",
                "started_at": timestamp,
                "ended_at": timestamp,
                "summary": content[:100] + "..." if len(content) > 100 else content,
                "tags": ["cursor", "ide"],
                "raw_content": content,
                "turns": [
                    {
                        "role": "assistant",
                        "content": content[:500],
                        "timestamp": timestamp
                    }
                ]
            }
        except Exception:
            return None
    
    def _parse_json_chat(self, data: list, filename: str) -> Optional[Dict]:
        """Parse a JSON chat log into a session dict."""
        try:
            if not data or not isinstance(data, list):
                return None
            
            # Look for message-like objects
            turns = []
            for item in data[:50]:  # Limit messages
                if isinstance(item, dict):
                    role = item.get('role', 'unknown')
                    content = item.get('content', item.get('message', item.get('text', '')))
                    if content:
                        turns.append({
                            "role": role if role in ['user', 'assistant', 'tool'] else 'assistant',
                            "content": str(content)[:1000],
                            "timestamp": item.get('timestamp', datetime.now().isoformat())
                        })
            
            if not turns:
                return None
            
            return {
                "tool": self.TOOL_NAME,
                "session_id": f"cursor_json_{filename}_{hash(str(data)) % 10000}",
                "started_at": turns[0].get("timestamp", datetime.now().isoformat()),
                "ended_at": turns[-1].get("timestamp", datetime.now().isoformat()),
                "summary": self._generate_summary(turns),
                "tags": ["cursor", "ide"],
                "raw_content": json.dumps(data),
                "turns": turns
            }
        except Exception:
            return None
    
    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate a one-line summary from conversation turns."""
        user_messages = [t["content"] for t in turns if t.get("role") == "user"]
        if user_messages:
            first_msg = user_messages[0]
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "Cursor IDE session"
    
    def get_stats(self) -> Dict[str, any]:
        """Return statistics about available Cursor data."""
        stats = super().get_stats()
        stats["data_dir"] = str(self.data_dir) if self.data_dir else None
        stats["platform"] = self.platform
        return stats
