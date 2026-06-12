"""TOON — Token-Optimized Object Notation for session state.

Produces ultra-compact, machine-parseable session summaries designed
for reinjection into AI context windows. Strips conversational filler,
keeps only signal.

Inspired by Robert Ruby II's TOON state file approach for managing
600k+ token contexts.
"""

import re
from typing import List, Dict, Optional
from datetime import datetime


class TOONCompactState:
    """Generates compact, token-efficient session snapshots.

    Output format is a structured dict that can be:
    - Serialized to JSON for machine consumption
    - Rendered as a dense markdown block for human reading
    - Embedded as a context injection at session start

    TOON strips:
    - Greetings, pleasantries, meta-discussion
    - Rephrased explanations of the same concept
    - Code blocks longer than needed for context
    - Tool call noise (keeps results, drops invocation chatter)

    TOON keeps:
    - Decisions with rationale
    - Files touched and why
    - Open threads (unresolved)
    - Next explicit steps
    - Key entities and their relationships
    - Blockers or warnings
    """

    def compact(self, session: Dict, intel: Dict = None) -> Dict:
        """Generate a TOON-compact representation of a session.

        Returns:
            {
                "toon_version": "1.0",
                "session_id": str,
                "workspace": str,
                "importance": int,
                "decisions": [...],
                "files": [...],
                "entities": [...],
                "open_threads": [...],
                "next_steps": [...],
                "blockers": [...],
                "context_summary": str,  # one dense paragraph
                "token_estimate": int,
            }
        """
        if intel is None:
            from .entities import EntityExtractor
            intel = EntityExtractor().extract_from_session(session)

        turns = session.get("turns", [])
        all_text = self._extract_signal_text(turns)

        return {
            "toon_version": "1.0",
            "session_id": session.get("session_id", "unknown"),
            "workspace": session.get("workspace", "unknown"),
            "importance": session.get("importance", 3),
            "timestamp": session.get("ended_at", datetime.now().isoformat()),
            "decisions": self._compact_decisions(intel.get("decisions", [])),
            "files": self._compact_files(intel.get("files", []), all_text),
            "entities": self._compact_entities(intel.get("entities", [])),
            "open_threads": self._extract_open_threads(turns),
            "next_steps": self._extract_next_steps(turns),
            "blockers": self._extract_blockers(turns),
            "context_summary": self._generate_context_summary(session, intel, all_text),
            "token_estimate": self._estimate_tokens(all_text),
        }

    def render_markdown(self, toon: Dict) -> str:
        """Render a TOON dict as a dense markdown block.

        Optimized for token efficiency: minimal formatting, no redundancy.
        """
        lines = [
            f"## {toon['session_id']} [{toon['importance']}/5]",
            f"Workspace: {toon['workspace']} | {toon['timestamp'][:10]}",
            "",
        ]

        if toon.get("context_summary"):
            lines.append(toon["context_summary"])
            lines.append("")

        if toon.get("decisions"):
            lines.append("D:")
            for d in toon["decisions"][:5]:
                lines.append(f"  • {d}")
            lines.append("")

        if toon.get("files"):
            lines.append("F:")
            for f in toon["files"][:8]:
                lines.append(f"  • {f}")
            lines.append("")

        if toon.get("next_steps"):
            lines.append("N:")
            for n in toon["next_steps"][:5]:
                lines.append(f"  → {n}")
            lines.append("")

        if toon.get("open_threads"):
            lines.append("O:")
            for o in toon["open_threads"][:5]:
                lines.append(f"  ? {o}")
            lines.append("")

        if toon.get("blockers"):
            lines.append("B:")
            for b in toon["blockers"][:3]:
                lines.append(f"  ! {b}")
            lines.append("")

        if toon.get("entities"):
            lines.append("E: " + ", ".join(toon["entities"][:10]))
            lines.append("")

        lines.append(f"~{toon.get('token_estimate', 0)} tokens")
        return "\n".join(lines)

    def render_injection(self, toon: Dict) -> str:
        """Render a single-paragraph injection string for agent context.

        Ultra-compact. Designed to be prepended to a new session
        so the agent knows where things left off.
        """
        parts = []

        if toon.get("context_summary"):
            parts.append(toon["context_summary"])

        if toon.get("decisions"):
            parts.append("Decided: " + "; ".join(toon["decisions"][:3]))

        if toon.get("next_steps"):
            parts.append("Next: " + "; ".join(toon["next_steps"][:3]))

        if toon.get("open_threads"):
            parts.append("Open: " + "; ".join(toon["open_threads"][:2]))

        if toon.get("files"):
            parts.append("Files: " + ", ".join(toon["files"][:5]))

        text = " | ".join(parts)
        if len(text) > 800:
            text = text[:797] + "..."
        return text

    def _extract_signal_text(self, turns: List[Dict]) -> str:
        """Extract only high-signal turns, strip noise."""
        signal_parts = []

        for turn in turns:
            role = turn.get("role", "")
            content = turn.get("content", "")

            # Skip greetings, meta, chitchat
            if self._is_noise(content):
                continue

            # Keep assistant substantive replies and user directives
            if role in ("assistant", "user"):
                signal_parts.append(content)

            # Keep tool results but not invocation noise
            if role == "tool" and len(content) < 500:
                signal_parts.append(content)

        return " ".join(signal_parts)

    def _is_noise(self, text: str) -> bool:
        """Check if text is conversational noise."""
        noise_patterns = [
            r'^(hi|hello|hey|greetings|thanks|thank you|ok|okay|sure|got it)[\s!.,]*$',
            r'^(let me know|any questions|feel free|no problem|you\'re welcome)[\s!.,]*$',
            r'^(great|awesome|perfect|nice|cool|sounds good)[\s!.,]*$',
        ]
        text_lower = text.lower().strip()
        return any(re.search(p, text_lower) for p in noise_patterns)

    def _compact_decisions(self, decisions: List[Dict]) -> List[str]:
        """Compress decisions to one-line strings."""
        compact = []
        for d in decisions[:5]:
            title = d.get("title", "").strip()
            decision = d.get("decision", "").strip()
            # Pick the shorter, more informative one
            if len(decision) < len(title) and len(decision) > 20:
                compact.append(decision[:120])
            else:
                compact.append(title[:120])
        return compact

    def _compact_files(self, files: List[str], context_text: str) -> List[str]:
        """List files with minimal context on why they were touched."""
        compact = []
        for f in files[:8]:
            # Try to find why this file was mentioned
            why = ""
            idx = context_text.lower().find(f.lower())
            if idx >= 0:
                snippet = context_text[max(0, idx-30):idx+len(f)+30]
                # Extract verb near file reference
                verb_match = re.search(r'(\w+(?:ed|ing|s))\s+(?:to|the|in)?\s*' + re.escape(f), snippet, re.IGNORECASE)
                if verb_match:
                    why = verb_match.group(1).lower()
            if why:
                compact.append(f"{f} ({why})")
            else:
                compact.append(f)
        return compact

    def _compact_entities(self, entities: List[Dict]) -> List[str]:
        """Return entity names only, deduplicated."""
        seen = set()
        result = []
        for e in entities:
            name = e.get("name", "")
            if name and name.lower() not in seen:
                seen.add(name.lower())
                result.append(name)
        return result

    def _extract_open_threads(self, turns: List[Dict]) -> List[str]:
        """Find unresolved items, open questions, pending work."""
        threads = []
        all_text = " ".join(t.get("content", "") for t in turns)

        # Pattern: "still need to", "pending", "TODO", "not yet"
        patterns = [
            r'(?:still|yet|not)\s+(?:need|have|resolved|implemented|figured)\s+(.{20,100})',
            r'(?:TODO|FIXME|OPEN|QUESTION):?\s*(.{20,100})',
            r'(?:we should|need to|should probably|might want to)\s+(.{20,100})(?=\.|$)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for m in matches[:3]:
                threads.append(m.strip())

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in threads:
            key = t.lower()[:40]
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique[:5]

    def _extract_next_steps(self, turns: List[Dict]) -> List[str]:
        """Extract explicit next actions."""
        steps = []
        all_text = " ".join(t.get("content", "") for t in turns)

        patterns = [
            r'(?:next step|next:|then we|after that|let\'s)\s+(.{20,100})',
            r'(?:we will|I will|plan to|going to)\s+(.{20,100})',
            r'(?:action item|next action):?\s*(.{20,100})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for m in matches[:3]:
                steps.append(m.strip())

        seen = set()
        unique = []
        for s in steps:
            key = s.lower()[:40]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique[:5]

    def _extract_blockers(self, turns: List[Dict]) -> List[str]:
        """Extract blockers, warnings, caveats."""
        blockers = []
        all_text = " ".join(t.get("content", "") for t in turns)

        patterns = [
            r'(?:blocker|blocked|stuck|cannot|unable to)\s+(.{20,100})',
            r'(?:warning|caution|note that|be aware)\s+(.{20,100})',
            r'(?:breaking change|deprecat|remov.*support)\s+(.{20,100})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for m in matches[:2]:
                blockers.append(m.strip())

        return blockers[:3]

    def _generate_context_summary(self, session: Dict, intel: Dict, signal_text: str) -> str:
        """Generate one dense paragraph of context."""
        tool = session.get("tool", "unknown")
        decisions = intel.get("decisions", [])
        files = intel.get("files", [])

        parts = [f"[{tool}]"]

        if decisions:
            d_text = decisions[0].get("title", "")[:80]
            parts.append(f"Decided: {d_text}")

        if files:
            parts.append(f"Touched {len(files)} files")

        # Extract topic from first substantive user message
        topic = self._extract_topic(signal_text)
        if topic:
            parts.append(f"Topic: {topic}")

        summary = " | ".join(parts)
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary

    def _extract_topic(self, text: str) -> str:
        """Extract the primary topic from session text."""
        # Look for "implement", "fix", "add", "refactor" + object
        match = re.search(
            r'\b(implement|fix|add|refactor|build|create|update|migrate)\s+(.{10,60})',
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(2).strip()
        return ""

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (~0.75 tokens per word for English)."""
        words = len(text.split())
        return int(words * 0.75)
