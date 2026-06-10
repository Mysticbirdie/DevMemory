"""Extractor for VS Code + GitHub Copilot Chat.

Reads from VS Code extension storage for Copilot chat history.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class VSCodeCopilotExtractor(BaseExtractor):
    """Extracts conversation history from VS Code + GitHub Copilot Chat."""
    
    TOOL_NAME = "vscode_copilot"
    DISPLAY_NAME = "VS Code + GitHub Copilot"
    
    # VS Code extension storage paths by platform
    EXTENSION_DIRS = {
        "darwin": Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage",
        "linux": Path.home() / ".config" / "Code" / "User" / "globalStorage",
        "win32": Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage",
    }
    
    def __init__(self, extension_dir: Optional[Path] = None):
        import sys
        self.platform = sys.platform
        self.extension_dir = extension_dir or self.EXTENSION_DIRS.get(self.platform)
    
    def is_available(self) -> bool:
        """Check if VS Code Copilot data is accessible."""
        if not self.extension_dir or not self.extension_dir.exists():
            return False
        
        # Check for Copilot extension
        copilot_dir = self.extension_dir / "github.copilot-chat"
        return copilot_dir.exists()
    
    def extract(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract sessions from VS Code Copilot Chat."""
        sessions = []
        
        copilot_dir = self.extension_dir / "github.copilot-chat"
        if not copilot_dir.exists():
            return sessions
        
        # Look for chat history files
        for history_file in copilot_dir.glob("**/*"):
            if history_file.is_file() and history_file.stat().st_size < 10_000_000:  # < 10MB
                try:
                    with open(history_file, 'r') as f:
                        content = f.read()
                    
                    # Try JSON first
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            session = self._parse_chat_history(data, history_file.name)
                            if session:
                                sessions.append(session)
                    except json.JSONDecodeError:
                        # Try line-delimited JSON
                        lines = content.strip().split('\n')
                        messages = []
                        for line in lines:
                            try:
                                msg = json.loads(line)
                                messages.append(msg)
                            except json.JSONDecodeError:
                                continue
                        
                        if messages:
                            session = self._parse_chat_history(messages, history_file.name)
                            if session:
                                sessions.append(session)
                                
                except Exception:
                    continue
        
        return sessions[:limit] if limit else sessions
    
    def _parse_chat_history(self, messages: list, filename: str) -> Optional[Dict]:
        """Parse chat messages into a session."""
        if not messages:
            return None
        
        turns = []
        for msg in messages[:100]:  # Limit messages
            if isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                content = msg.get('content', msg.get('message', msg.get('text', '')))
                if content:
                    turns.append({
                        "role": role if role in ['user', 'assistant', 'tool'] else 'assistant',
                        "content": str(content)[:1000],
                        "timestamp": msg.get('timestamp', datetime.now().isoformat())
                    })
        
        if not turns:
            return None
        
        return {
            "tool": self.TOOL_NAME,
            "session_id": f"copilot_{filename}_{hash(str(messages)) % 10000}",
            "started_at": datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "summary": self._generate_summary(turns),
            "tags": ["vscode", "copilot", "github"],
            "raw_content": json.dumps(messages),
            "turns": turns
        }
    
    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate summary from conversation turns."""
        user_messages = [t["content"] for t in turns if t.get("role") == "user"]
        if user_messages:
            first_msg = user_messages[0]
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "VS Code Copilot session"
