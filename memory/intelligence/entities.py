"""Entity extraction from sessions."""

import re
from typing import List, Dict, Set, Tuple
from collections import Counter


# Known technical entities (expandable)
KNOWN_TECH = {
    'stella', 'triad', 'redis', 'firebase', 'postgresql', 'supabase',
    'react', 'typescript', 'python', 'fastapi', 'docker', 'kubernetes',
    'mongodb', 'sqlite', 'graphql', 'rest', 'api', 'websocket',
    'tailwind', 'css', 'html', 'javascript', 'node', 'npm',
    'git', 'github', 'ci', 'cd', 'pipeline', 'deployment',
    'testing', 'pytest', 'jest', 'cypress', 'playwright',
    'llm', 'openai', 'anthropic', 'claude', 'mistral',
    'embedding', 'vector', 'rag', 'prompt', 'token',
    'async', 'await', 'promise', 'callback', 'hook',
    'component', 'service', 'router', 'middleware', 'controller',
    'schema', 'migration', 'model', 'serializer', 'validator',
}

# File patterns
FILE_PATTERNS = [
    r'\b[\w\-]+\.(py|ts|tsx|js|jsx|json|yaml|yml|md|sql|sh|dockerfile)\b',
    r'\b[A-Z][a-zA-Z]+\.(py|ts|tsx)\b',  # PascalCase files (components)
]

# Bug/issue patterns
BUG_PATTERNS = [
    r'\b(race condition|memory leak|null pointer|segfault|deadlock)\b',
    r'\b(bug|issue|error|exception|crash|failure|broken)\b',
]

# Decision patterns
DECISION_PATTERNS = [
    r'\b(decided|decision|chose|chosen|opted|approach)\b',
    r'\b(we will|we should|let\'s|going to|plan to)\b',
]


class EntityExtractor:
    """Extracts entities, decisions, and patterns from sessions."""
    
    def __init__(self):
        self.entities: Dict[str, Dict] = {}
    
    def extract_from_session(self, session: Dict) -> Dict:
        """Extract all intelligence from a session.
        
        Returns:
            {
                "entities": List[{"name": str, "type": str, "context": str}],
                "decisions": List[{"title": str, "context": str, "decision": str}],
                "patterns": List[{"type": str, "description": str}],
                "files": List[str],
                "tags": List[str]
            }
        """
        result = {
            "entities": [],
            "decisions": [],
            "patterns": [],
            "files": [],
            "tags": []
        }
        
        # Combine all text from turns
        all_text = " ".join(
            t.get("content", "") for t in session.get("turns", [])
        )
        
        # Extract entities
        result["entities"] = self._extract_entities(all_text)
        
        # Extract decisions
        result["decisions"] = self._extract_decisions(all_text, session)
        
        # Extract patterns
        result["patterns"] = self._extract_patterns(all_text, session)
        
        # Extract files
        result["files"] = self._extract_files(all_text, session)
        
        # Extract tags
        result["tags"] = self._extract_tags(all_text)
        
        return result
    
    def _extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities from text."""
        entities = []
        text_lower = text.lower()
        
        # Known technical entities
        for tech in KNOWN_TECH:
            if tech in text_lower:
                # Find context
                idx = text_lower.find(tech)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(tech) + 50)
                context = text[start:end]
                
                entities.append({
                    "name": tech,
                    "type": "technology",
                    "context": context
                })
        
        # Extract potential proper nouns (project names, people)
        # Pattern: Capitalized words in technical contexts
        proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text)
        for noun in set(proper_nouns):
            if len(noun) > 3 and noun.lower() not in KNOWN_TECH:
                entities.append({
                    "name": noun,
                    "type": "concept",
                    "context": ""
                })
        
        # File references
        file_refs = re.findall(r'`([^`]+\.(py|ts|tsx|js|jsx|md|json))`', text)
        for ref in file_refs:
            entities.append({
                "name": ref[0],
                "type": "file",
                "context": ""
            })
        
        return entities
    
    def _extract_decisions(self, text: str, session: Dict) -> List[Dict]:
        """Extract architectural decisions from text."""
        decisions = []
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            
            # Look for decision indicators
            is_decision = any(
                re.search(pattern, sentence, re.IGNORECASE)
                for pattern in DECISION_PATTERNS
            )
            
            if is_decision and len(sentence) < 500:
                decisions.append({
                    "title": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                    "context": session.get("summary", ""),
                    "decision": sentence
                })
        
        return decisions[:5]  # Limit to top 5
    
    def _extract_patterns(self, text: str, session: Dict) -> List[Dict]:
        """Extract code patterns and fixes."""
        patterns = []
        
        # Bug fixes
        if any(re.search(p, text, re.IGNORECASE) for p in BUG_PATTERNS):
            # Find the fix context
            fix_match = re.search(
                r'(?:fixed|fix|resolved|solved|patched)\s+(.{50,300})',
                text,
                re.IGNORECASE
            )
            if fix_match:
                patterns.append({
                    "type": "fix",
                    "description": fix_match.group(1).strip()
                })
        
        # Refactoring patterns
        refactor_match = re.search(
            r'(?:refactor|restructure|reorganize|simplify)\s+(.{50,300})',
            text,
            re.IGNORECASE
        )
        if refactor_match:
            patterns.append({
                "type": "refactor",
                "description": refactor_match.group(1).strip()
            })
        
        # Code examples in backticks or code blocks
        code_blocks = re.findall(r'```\w*\n(.*?)```', text, re.DOTALL)
        for block in code_blocks[:2]:  # Limit to first 2
            if len(block) > 50:
                patterns.append({
                    "type": "code_example",
                    "description": block[:200] + "..."
                })
        
        return patterns
    
    def _extract_files(self, text: str, session: Dict) -> List[str]:
        """Extract file references."""
        files = set()
        
        # Inline code references
        inline_files = re.findall(r'`([^`]+\.(py|ts|tsx|js|jsx|md|json|yaml))`', text)
        for match in inline_files:
            files.add(match[0])
        
        # File path mentions
        path_files = re.findall(r'(?:file|path|in)\s+[`\']?(?:\./)?([\w/\-]+\.(?:py|ts|tsx|js|jsx|md))', text, re.IGNORECASE)
        files.update(path_files)
        
        # From git turns
        for turn in session.get("turns", []):
            if "files_changed" in turn:
                for f in turn["files_changed"]:
                    if isinstance(f, dict):
                        files.add(f.get("path", ""))
                    elif isinstance(f, str):
                        files.add(f)
        
        return sorted(f for f in files if f)
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extract topic tags."""
        text_lower = text.lower()
        tags = Counter()
        
        # Technical areas
        tech_areas = {
            'frontend': ['react', 'component', 'ui', 'css', 'html', 'dom'],
            'backend': ['api', 'server', 'endpoint', 'route', 'database'],
            'devops': ['docker', 'deploy', 'pipeline', 'ci', 'cd', 'kubernetes'],
            'testing': ['test', 'pytest', 'jest', 'spec', 'coverage'],
            'database': ['sql', 'postgres', 'mongodb', 'migration', 'schema'],
            'ai': ['llm', 'prompt', 'embedding', 'model', 'agent', 'rag'],
            'security': ['auth', 'token', 'secret', 'sanitize', 'injection'],
            'performance': ['optimize', 'speed', 'cache', 'memory', 'slow'],
            'bugfix': ['bug', 'fix', 'error', 'crash', 'broken'],
            'feature': ['feat', 'add', 'implement', 'new', 'create'],
        }
        
        for area, keywords in tech_areas.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                tags[area] = score
        
        # Return top tags
        return [tag for tag, _ in tags.most_common(5)]


def extract_entity_links(entities: List[Dict]) -> List[Tuple[str, str, float]]:
    """Extract co-occurrence links between entities.
    
    Returns list of (entity_a, entity_b, strength) tuples.
    """
    links = []
    entity_names = [e["name"] for e in entities]
    
    # Simple co-occurrence: entities mentioned in same session are linked
    for i, a in enumerate(entity_names):
        for b in entity_names[i+1:]:
            links.append((a, b, 1.0))
    
    return links
