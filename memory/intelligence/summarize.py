"""Session summarization."""

import re
from typing import List, Dict


class SessionSummarizer:
    """Generates summaries from sessions."""
    
    def summarize(self, session: Dict) -> str:
        """Generate a one-line summary of a session."""
        turns = session.get("turns", [])
        
        if not turns:
            return "Empty session"
        
        # Get first user message as primary context
        user_messages = [t["content"] for t in turns if t.get("role") in ("user", "developer")]
        
        if user_messages:
            first_msg = user_messages[0].strip()
            
            # Extract first sentence or first 100 chars
            first_sentence = re.split(r'[.!?]', first_msg)[0]
            summary = first_sentence[:120]
            
            if len(first_sentence) > 120:
                summary += "..."
            
            return summary
        
        # Fall back to any content
        first_content = turns[0].get("content", "")
        return first_content[:120] + ("..." if len(first_content) > 120 else "")
    
    def extract_key_points(self, session: Dict) -> List[str]:
        """Extract key points/decisions from a session."""
        points = []
        turns = session.get("turns", [])
        
        all_text = " ".join(t.get("content", "") for t in turns)
        sentences = re.split(r'[.!?]+', all_text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            
            # Look for key indicators
            indicators = [
                r'\b(decided|decision|conclusion|outcome|result)\b',
                r'\b(important|critical|key|main|primary)\b',
                r'\b(should|must|need to|going to|will)\b',
                r'\b(fixed|solved|resolved|completed|done)\b',
            ]
            
            if any(re.search(i, sentence, re.IGNORECASE) for i in indicators):
                points.append(sentence[:150] + ("..." if len(sentence) > 150 else ""))
        
        return points[:5]  # Top 5
    
    def extract_action_items(self, session: Dict) -> List[str]:
        """Extract action items / TODOs."""
        items = []
        turns = session.get("turns", [])
        
        all_text = " ".join(t.get("content", "") for t in turns)
        
        # Match TODO patterns
        todos = re.findall(
            r'(?:TODO|FIXME|XXX|HACK|ACTION|NEXT):?\s*(.+?)(?=\n|$)',
            all_text,
            re.IGNORECASE
        )
        
        for todo in todos:
            items.append(todo.strip()[:200])
        
        # Match "we need to" / "next step" patterns
        needs = re.findall(
            r'(?:we need to|next step|should|let\'s)\s+(.{20,150}?)(?=\.|$)',
            all_text,
            re.IGNORECASE
        )
        
        for need in needs:
            items.append(need.strip())
        
        return items[:10]
