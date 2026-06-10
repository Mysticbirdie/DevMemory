"""Base extractor class for all IDE/CLI tools.

All extractors inherit from BaseExtractor and implement:
- is_available() -> bool
- extract(limit=None, dry_run=False) -> List[Dict]

This makes it trivial to add new IDEs or tools.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path


class BaseExtractor(ABC):
    """Abstract base class for all DevMemory extractors."""
    
    # Tool identifier used in session records
    TOOL_NAME: str = "unknown"
    
    # Human-readable name
    DISPLAY_NAME: str = "Unknown Tool"
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this tool's data is accessible on the current system."""
        pass
    
    @abstractmethod
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        """Extract sessions from this tool.
        
        Args:
            limit: Max sessions to extract
            dry_run: If True, preview what would be extracted without returning full data
            
        Returns list of session dicts with format:
        {
            "tool": str,           # TOOL_NAME
            "session_id": str,
            "started_at": str,     # ISO datetime
            "ended_at": str,
            "summary": str,
            "tags": list,
            "raw_content": str,
            "turns": [
                {
                    "role": "user" | "assistant" | "tool",
                    "content": str,
                    "timestamp": str
                }
            ]
        }
        """
        pass
    
    def get_stats(self) -> Dict:
        """Return statistics about available data."""
        return {
            "tool": self.TOOL_NAME,
            "display_name": self.DISPLAY_NAME,
            "available": self.is_available(),
        }
    
    def validate_session(self, session: Dict) -> bool:
        """Validate a session has minimum required data."""
        if not session:
            return False
        
        turns = session.get("turns", [])
        if len(turns) < 2:
            return False
        
        # Check at least one turn has content
        has_content = any(t.get("content") for t in turns if isinstance(t, dict))
        if not has_content:
            return False
        
        return True
    
    def filter_valid_sessions(self, sessions: List[Dict]) -> List[Dict]:
        """Filter out invalid sessions."""
        valid = []
        for session in sessions:
            if self.validate_session(session):
                valid.append(session)
            # else: silently drop invalid sessions
        return valid
