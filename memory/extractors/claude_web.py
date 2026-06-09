"""Extractor for Claude Web (claude.ai) exported conversations.

Claude Web has an "Export chat" button that produces JSON.
This parser imports those exports into DevMemory.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class ClaudeWebExtractor:
    """Extracts conversation history from Claude Web exports."""
    
    def __init__(self, export_dir: Optional[Path] = None):
        """Initialize with directory to watch for exports.
        
        Default: ~/Downloads (where browser saves exports)
        """
        self.export_dir = export_dir or (Path.home() / "Downloads")
        self.sessions: List[Dict] = []
    
    def find_exports(self) -> List[Path]:
        """Find Claude Web export files in the export directory.
        
        Claude Web exports are named: "Claude Chat - YYYY-MM-DD HH-MM-SS.json"
        """
        if not self.export_dir.exists():
            return []
        
        pattern = "Claude Chat - *.json"
        return sorted(self.export_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    
    def extract(self, limit: Optional[int] = None, specific_file: Optional[Path] = None) -> List[Dict]:
        """Extract sessions from Claude Web export files.
        
        Args:
            limit: Max number of export files to process
            specific_file: Process only this specific file (optional)
        
        Returns list of session dicts.
        """
        sessions = []
        
        if specific_file:
            files = [specific_file] if specific_file.exists() else []
        else:
            files = self.find_exports()
            if limit:
                files = files[:limit]
        
        for export_file in files:
            try:
                session = self._parse_export(export_file)
                if session:
                    sessions.append(session)
            except Exception as e:
                print(f"Warning: Could not parse {export_file}: {e}")
        
        return sessions
    
    def _parse_export(self, export_file: Path) -> Optional[Dict]:
        """Parse a Claude Web export JSON file."""
        data = json.loads(export_file.read_text())
        
        # Claude Web export format:
        # {
        #   "name": "Chat title",
        #   "created_at": "2026-06-08T14:30:00.000Z",
        #   "messages": [
        #     {"role": "user", "content": "..."},
        #     {"role": "assistant", "content": "..."}
        #   ]
        # }
        
        if not isinstance(data, dict):
            return None
        
        messages = data.get("messages", [])
        if not messages:
            return None
        
        # Convert to turns format
        turns = []
        for msg in messages:
            if isinstance(msg, dict):
                # Handle content (could be string or list of content blocks)
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Extract text from content blocks
                    texts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                texts.append(block.get("text", ""))
                    content = "\n".join(texts)
                
                turns.append({
                    "role": msg.get("role", "unknown"),
                    "content": content,
                    "timestamp": msg.get("created_at", datetime.now().isoformat())
                })
        
        if not turns:
            return None
        
        # Extract session info
        created_at = data.get("created_at", datetime.now().isoformat())
        name = data.get("name", export_file.stem)
        uuid = data.get("uuid", export_file.stem)
        
        return {
            "tool": "claude_web",
            "session_id": f"claude_web_{uuid}",
            "started_at": created_at,
            "ended_at": turns[-1].get("timestamp", created_at) if turns else created_at,
            "summary": name or self._generate_summary(turns),
            "tags": self._extract_tags(turns),
            "raw_content": json.dumps(turns),
            "turns": turns,
            "source_file": str(export_file.name)
        }
    
    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate a one-line summary from conversation turns."""
        user_messages = [t["content"] for t in turns if t.get("role") == "user"]
        if user_messages:
            first_msg = user_messages[0].strip()
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "Claude Web chat"
    
    def _extract_tags(self, turns: List[Dict]) -> List[str]:
        """Extract tags from conversation content."""
        all_text = " ".join(t["content"] for t in turns if t.get("content"))[:5000]
        
        tech_patterns = [
            r'\b(Stella|Triad|Redis|Firebase|PostgreSQL|Supabase)\b',
            r'\b(React|TypeScript|Python|FastAPI|Docker|Kubernetes)\b',
            r'\b(bug|fix|debug|error|issue|refactor|optimize)\b',
            r'\b(feature|implement|add|create|build|design)\b',
            r'\b(architecture|database|api|frontend|backend|devops)\b',
            r'\b(llm|ai|model|prompt|embedding|vector|rag)\b',
        ]
        
        tags = set()
        for pattern in tech_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            tags.update(m.lower() for m in matches)
        
        return list(tags)[:10]
    
    def watch_and_import(self, auto_import: bool = False) -> List[Dict]:
        """Watch for new exports and optionally auto-import them.
        
        Args:
            auto_import: If True, automatically import all found exports.
                        If False, just list them and ask for confirmation.
        
        Returns imported sessions.
        """
        exports = self.find_exports()
        
        if not exports:
            print("No Claude Web exports found in ~/Downloads")
            print("Export a chat from claude.ai first (3-dot menu → Export chat)")
            return []
        
        print(f"\n🌐 Found {len(exports)} Claude Web export(s):")
        for i, export in enumerate(exports, 1):
            mtime = datetime.fromtimestamp(export.stat().st_mtime)
            size = export.stat().st_size
            print(f"  {i}. {export.name} ({size//1024}KB, {mtime.strftime('%Y-%m-%d %H:%M')})")
        
        if not auto_import:
            print("\nTo import, run:")
            print(f"  python3 cli.py import-web --file \"{exports[0]}\"")
            print(f"  python3 cli.py import-web --all")
            return []
        
        print("\n📥 Auto-importing...")
        return self.extract()
