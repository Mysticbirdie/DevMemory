"""Extractor for Aider CLI sessions.

Aider is a CLI tool for pair programming with LLMs.
Reads from Aider's chat history files.
https://aider.chat/
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class AiderExtractor(BaseExtractor):
    """Extracts conversation history from Aider CLI."""
    
    TOOL_NAME = "aider"
    DISPLAY_NAME = "Aider (CLI Pair Programming)"
    
    # Aider stores history in various locations
    HISTORY_DIRS = [
        Path.home() / ".aider",
        Path.cwd() / ".aider",
    ]
    
    def __init__(self, history_dir: Optional[Path] = None):
        self.history_dir = history_dir
        self.sessions: List[Dict] = []
    
    def is_available(self) -> bool:
        """Check if Aider history is accessible."""
        # Check environment variable first
        aider_dir = os.environ.get('AIDER_DIR')
        if aider_dir and Path(aider_dir).exists():
            return True
        
        # Check standard locations
        for directory in self.HISTORY_DIRS:
            if directory.exists():
                return True
        
        return False
    
    def extract(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract sessions from Aider history."""
        sessions = []
        
        # Find Aider directory
        aider_dir = self._find_aider_dir()
        if not aider_dir:
            return sessions
        
        # Look for chat history files
        for history_file in aider_dir.glob("**/*"):
            if history_file.is_file() and history_file.suffix in ['.json', '.jsonl', '.md', '.txt']:
                try:
                    with open(history_file, 'r') as f:
                        content = f.read()
                    
                    # Try JSON
                    if history_file.suffix == '.json':
                        data = json.loads(content)
                        if isinstance(data, list):
                            session = self._parse_json_history(data, history_file.name)
                            if session:
                                sessions.append(session)
                    
                    # Try JSONL
                    elif history_file.suffix == '.jsonl':
                        messages = []
                        for line in content.strip().split('\n'):
                            try:
                                msg = json.loads(line)
                                messages.append(msg)
                            except json.JSONDecodeError:
                                continue
                        if messages:
                            session = self._parse_json_history(messages, history_file.name)
                            if session:
                                sessions.append(session)
                    
                    # Try Markdown (Aider often uses .md for chat logs)
                    elif history_file.suffix in ['.md', '.txt']:
                        session = self._parse_markdown_chat(content, history_file.name)
                        if session:
                            sessions.append(session)
                                
                except Exception:
                    continue
        
        return sessions[:limit] if limit else sessions
    
    def _find_aider_dir(self) -> Optional[Path]:
        """Find the Aider data directory."""
        # Check environment variable
        aider_dir = os.environ.get('AIDER_DIR')
        if aider_dir:
            path = Path(aider_dir)
            if path.exists():
                return path
        
        # Check standard locations
        for directory in self.HISTORY_DIRS:
            if directory.exists():
                return directory
        
        return None
    
    def _parse_json_history(self, messages: list, filename: str) -> Optional[Dict]:
        """Parse JSON chat history."""
        if not messages:
            return None
        
        turns = []
        for msg in messages[:100]:
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
            "session_id": f"aider_{filename}_{hash(str(messages)) % 10000}",
            "started_at": datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "summary": self._generate_summary(turns),
            "tags": ["aider", "cli", "pair-programming"],
            "raw_content": json.dumps(messages),
            "turns": turns
        }
    
    def _parse_markdown_chat(self, content: str, filename: str) -> Optional[Dict]:
        """Parse markdown chat log."""
        lines = content.split('\n')
        turns = []
        current_role = None
        current_content = []
        
        for line in lines:
            # Aider format: "#### >" for user, "####" for assistant
            if line.startswith('#### >'):
                # Save previous turn
                if current_role and current_content:
                    turns.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip(),
                        "timestamp": datetime.now().isoformat()
                    })
                current_role = "user"
                current_content = [line[6:].strip()]
            elif line.startswith('#### ') and not line.startswith('#### >'):
                if current_role and current_content:
                    turns.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip(),
                        "timestamp": datetime.now().isoformat()
                    })
                current_role = "assistant"
                current_content = [line[5:].strip()]
            elif current_role:
                current_content.append(line)
        
        # Save last turn
        if current_role and current_content:
            turns.append({
                "role": current_role,
                "content": '\n'.join(current_content).strip(),
                "timestamp": datetime.now().isoformat()
            })
        
        if not turns:
            return None
        
        return {
            "tool": self.TOOL_NAME,
            "session_id": f"aider_md_{filename}_{hash(content) % 10000}",
            "started_at": datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "summary": self._generate_summary(turns),
            "tags": ["aider", "cli", "pair-programming"],
            "raw_content": content,
            "turns": turns
        }
    
    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate summary from turns."""
        user_messages = [t["content"] for t in turns if t.get("role") == "user"]
        if user_messages:
            first_msg = user_messages[0]
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "Aider pair programming session"
