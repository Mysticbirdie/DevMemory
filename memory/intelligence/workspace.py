"""Workspace inference for sessions.

Infers which project/department a session belongs to based on:
- Git repository name
- File paths in session content
- Working directory hints
- Explicit tags or metadata
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Optional


class WorkspaceInferrer:
    """Infers workspace/department from session content and context."""

    # Common non-project directories to ignore
    IGNORED_DIRS = {
        'downloads', 'documents', 'desktop', 'tmp', 'temp',
        'home', 'users', 'root', 'workspace', 'projects',
    }

    def infer(self, session: Dict) -> Optional[str]:
        """Try to determine workspace from session data.

        Priority:
        1. Explicit workspace field already set
        2. Git repo name from file paths
        3. Most common directory name from file references
        4. Tool-specific hints (e.g., VS Code workspace)
        """
        # Already set
        if session.get("workspace"):
            return session["workspace"]

        all_text = " ".join(
            t.get("content", "") for t in session.get("turns", [])
        )

        # Try git repo from paths
        repo = self._extract_git_repo(all_text)
        if repo:
            return repo

        # Try common directory patterns
        workspace = self._extract_from_paths(all_text)
        if workspace:
            return workspace

        # Try current working directory from tool context
        cwd = self._extract_cwd(session)
        if cwd:
            return cwd

        # Fallback: tool name as department
        tool = session.get("tool", "unknown")
        if tool != "unknown":
            return tool

        return None

    def _extract_git_repo(self, text: str) -> Optional[str]:
        """Extract git repo name from path patterns."""
        # Match /path/to/repo-name/.git or /path/to/repo-name/src/...
        patterns = [
            r'[/\\]([^/\\]+)[/\\]\.git',
            r'[/\\]github\.com[/\\][^/\\]+[/\\]([^/\\\s]+)',
            r'[/\\]gitlab\.com[/\\][^/\\]+[/\\]([^/\\\s]+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                if m.lower() not in self.IGNORED_DIRS and len(m) > 2:
                    return m
        return None

    def _extract_from_paths(self, text: str) -> Optional[str]:
        """Find most frequent project directory from file paths."""
        # Extract paths like /Users/name/ProjectName/src/... or ./project-name/
        path_patterns = [
            r'(?:[/\\]|[\s]|^)([A-Z][a-zA-Z0-9_-]{2,30})[/\\](?:src|app|lib|components|pages)',
            r'(?:[/\\]|[\s]|^)([a-z][a-z0-9_-]{2,30})[/\\](?:src|app|lib|components|pages)',
        ]

        candidates = []
        for pattern in path_patterns:
            matches = re.findall(pattern, text)
            candidates.extend(m for m in matches if m.lower() not in self.IGNORED_DIRS)

        if candidates:
            # Return most common
            from collections import Counter
            return Counter(candidates).most_common(1)[0][0]

        # Try simpler: just look for directory-like names before file extensions
        simple_dirs = re.findall(r'[/\\]([A-Za-z][\w-]{2,30})[/\\][\w-]+\.(py|ts|tsx|js|jsx|rs)', text)
        if simple_dirs:
            from collections import Counter
            return Counter([d[0] for d in simple_dirs]).most_common(1)[0][0]

        return None

    def _extract_cwd(self, session: Dict) -> Optional[str]:
        """Extract current working directory from session metadata."""
        # Check turns for explicit cwd mentions
        for turn in session.get("turns", []):
            content = turn.get("content", "")
            # Match "current directory", "working directory", "repo"
            match = re.search(
                r'(?:current|working)\s+directory[:\s]+[`\']?([^\s\'`\n]+)',
                content,
                re.IGNORECASE
            )
            if match:
                path = match.group(1)
                name = Path(path).name
                if name.lower() not in self.IGNORED_DIRS:
                    return name

            # Check for explicit repo references
            match = re.search(
                r'(?:repo|repository|project)[:\s]+[`\']?([^\s\'`\n]+)',
                content,
                re.IGNORECASE
            )
            if match:
                return match.group(1)

        return None
