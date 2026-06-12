"""Importance scoring for sessions.

Scores sessions 1-5 based on signal density:
- Decisions made
- Files touched
- Pattern richness
- Tool type weighting
- Conversation depth
"""

import re
from typing import List, Dict


class ImportanceScorer:
    """Scores session importance on a 1-5 scale.

    1 = Trivial (chitchat, simple lookups)
    2 = Minor (small fixes, one-liner changes)
    3 = Moderate (routine work, few files)
    4 = Significant (architecture decisions, multi-file refactor)
    5 = Critical (major design choice, breaking change, complex bug fix)
    """

    def score(self, session: Dict, intel: Dict = None) -> int:
        """Calculate importance score for a session.

        Args:
            session: Session dict with turns, summary, etc.
            intel: Pre-extracted intelligence (entities, decisions, patterns, files)
                   If None, extracts from session on the fly.

        Returns:
            int: Score from 1 to 5
        """
        score = 1  # baseline

        # Get intelligence if not provided
        if intel is None:
            from .entities import EntityExtractor
            intel = EntityExtractor().extract_from_session(session)

        # Decision density (highest signal)
        decision_count = len(intel.get("decisions", []))
        if decision_count >= 3:
            score += 2
        elif decision_count >= 1:
            score += 1

        # File activity
        file_count = len(intel.get("files", []))
        if file_count >= 10:
            score += 1
        if file_count >= 5:
            score += 1
        elif file_count >= 2:
            score += 0

        # Pattern richness
        pattern_count = len(intel.get("patterns", []))
        if pattern_count >= 2:
            score += 1

        # Conversation depth (signal of real work vs chitchat)
        turns = session.get("turns", [])
        if len(turns) >= 10:
            score += 1
        elif len(turns) >= 5:
            score += 0

        # Tool type weighting
        tool = session.get("tool", "")
        tool_boost = {
            "git": 0,           # Commits are usually lower signal
            "ollama": 0,        # Model queries are low signal
            "vscode_copilot": 0, # Copilot chats vary
        }.get(tool, 1)  # Most IDEs/CLIs get +1
        score += tool_boost

        # Content heuristics
        all_text = " ".join(t.get("content", "") for t in turns)
        if self._has_architectural_keywords(all_text):
            score += 1
        if self._has_bug_keywords(all_text):
            score += 1
        if self._has_refactor_keywords(all_text):
            score += 1

        return min(5, max(1, int(score)))

    def _has_architectural_keywords(self, text: str) -> bool:
        """Check for architecture-level keywords."""
        keywords = [
            r'\b(architecture|architectural|design pattern|refactor to|restructure|migrate to)\b',
            r'\b(breaking change|api version|backward compat|deprecat)\b',
            r'\b(introduce|adopt|switch to|move to|consolidate|unify)\b',
        ]
        text_lower = text.lower()
        return any(re.search(k, text_lower) for k in keywords)

    def _has_bug_keywords(self, text: str) -> bool:
        """Check for bug-fix indicators."""
        keywords = [
            r'\b(race condition|memory leak|deadlock|segfault|null pointer)\b',
            r'\b(root cause|regression|hotfix|critical bug|production issue)\b',
        ]
        text_lower = text.lower()
        return any(re.search(k, text_lower) for k in keywords)

    def _has_refactor_keywords(self, text: str) -> bool:
        """Check for significant refactoring."""
        keywords = [
            r'\b(rewrite|extract module|split into|merge.*into|consolidate)\b',
            r'\b(eliminate duplicate|dry principle|separation of concerns)\b',
        ]
        text_lower = text.lower()
        return any(re.search(k, text_lower) for k in keywords)

    def explain(self, session: Dict, intel: Dict = None) -> Dict:
        """Return score with explanation for transparency."""
        score = self.score(session, intel)
        if intel is None:
            from .entities import EntityExtractor
            intel = EntityExtractor().extract_from_session(session)

        return {
            "score": score,
            "factors": {
                "decisions": len(intel.get("decisions", [])),
                "files": len(intel.get("files", [])),
                "patterns": len(intel.get("patterns", [])),
                "turns": len(session.get("turns", [])),
                "tool": session.get("tool", "unknown"),
            },
            "rationale": self._rationale(score, session, intel)
        }

    def _rationale(self, score: int, session: Dict, intel: Dict) -> str:
        """Generate human-readable rationale."""
        parts = []
        if len(intel.get("decisions", [])) >= 2:
            parts.append(f"{len(intel['decisions'])} decisions")
        if len(intel.get("files", [])) >= 5:
            parts.append(f"{len(intel['files'])} files touched")
        if len(session.get("turns", [])) >= 10:
            parts.append("deep conversation")
        if not parts:
            parts.append("routine session")

        label = {1: "Trivial", 2: "Minor", 3: "Moderate", 4: "Significant", 5: "Critical"}.get(score, "Unknown")
        return f"{label}: {', '.join(parts)}"
