"""Base extractor class for all IDE/CLI tools.

All extractors inherit from BaseExtractor and implement:
- is_available() -> bool
- extract(limit=None) -> List[Dict]

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
    def extract(self, limit: Optional[int] = None) -> List[Dict]:
        """Extract sessions from this tool.
        
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
    
    def get_stats(self) -> Dict[str, any]:
        """Return statistics about available data."""
        return {
            "tool": self.TOOL_NAME,
            "available": self.is_available(),
            "display_name": self.DISPLAY_NAME,
        }
