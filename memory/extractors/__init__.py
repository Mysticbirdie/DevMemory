"""Extractors for reading data from AI coding tools, CLIs, and Git.

Supported tools:
- Devin Local (VS Code extension)
- Cursor IDE (VS Code fork)
- VS Code + GitHub Copilot Chat
- Aider (CLI pair programming)
- Claude CLI
- Claude Web (claude.ai exports)
- Git
"""

from .base import BaseExtractor
from .devin_local import DevinLocalExtractor
from .cursor import CursorExtractor
from .vscode_copilot import VSCodeCopilotExtractor
from .aider import AiderExtractor
from .claude_cli import ClaudeCLIExtractor
from .claude_web import ClaudeWebExtractor
from .git import GitExtractor

__all__ = [
    "BaseExtractor",
    "DevinLocalExtractor",
    "CursorExtractor", 
    "VSCodeCopilotExtractor",
    "AiderExtractor",
    "ClaudeCLIExtractor",
    "ClaudeWebExtractor",
    "GitExtractor",
]
