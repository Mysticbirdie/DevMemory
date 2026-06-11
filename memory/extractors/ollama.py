"""Extractor for Ollama local and cloud model usage.

Reads from Ollama's local API (http://localhost:11434) and detects
cloud models. Ollama doesn't store conversation history natively, so
this extractor captures model inventory, usage patterns, and any
available chat exports from common client locations.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import urllib.request
import urllib.error
from .base import BaseExtractor


class OllamaExtractor(BaseExtractor):
    """Extracts Ollama model activity and usage patterns."""

    TOOL_NAME = "ollama"
    DISPLAY_NAME = "Ollama (Local + Cloud)"

    # Ollama API endpoints
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_DIR = Path.home() / ".ollama"

    # Common chat history locations for Ollama clients
    CHAT_HISTORY_PATHS = [
        Path.home() / "Library" / "Application Support" / "Ollama",
        Path.home() / ".config" / "Ollama",
        Path.home() / ".local" / "share" / "Ollama",
    ]

    # Models to exclude (not coding-focused or not consumer-hardware friendly)
    EXCLUDED_MODELS = ["mistral", "bielik"]

    # Coding-capable model families that run well on consumer hardware
    CODING_MODELS = [
        "qwen", "codellama", "deepseek", "phi", "gemma", "codegeex",
        "starcoder", "wizardcoder", "phind", "openchat", "neural-chat",
        "dolphin", "solar", "tinyllama", "orca", "vicuna"
    ]

    def __init__(self, host: Optional[str] = None):
        self.host = host or self.OLLAMA_HOST
        self.models: List[Dict] = []
        self._fetch_models()

    def _fetch_models(self) -> None:
        """Fetch available models from Ollama API."""
        try:
            req = urllib.request.Request(
                f"{self.host}/api/tags",
                headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.models = data.get("models", [])
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
            self.models = []

    def is_available(self) -> bool:
        """Check if Ollama API is accessible (local or cloud)."""
        return len(self.models) > 0 or self.OLLAMA_DIR.exists()

    def get_stats(self) -> Dict:
        """Return statistics about Ollama models."""
        stats = super().get_stats()

        filtered = self._filter_models(self.models)
        local_models = [m for m in filtered if not self._is_cloud_model(m)]
        cloud_models = [m for m in filtered if self._is_cloud_model(m)]
        coding_models = [m for m in filtered if self._is_coding_model(m)]

        stats["total_models"] = len(self.models)
        stats["relevant_models"] = len(filtered)
        stats["excluded_models"] = len(self.models) - len(filtered)
        stats["local_models"] = len(local_models)
        stats["cloud_models"] = len(cloud_models)
        stats["coding_models"] = len(coding_models)
        stats["model_names"] = [m.get("name", "unknown") for m in filtered]
        stats["excluded_names"] = [m.get("name", "unknown") for m in self.models if self._is_excluded_model(m)]
        stats["host"] = self.host
        stats["ollama_dir_exists"] = self.OLLAMA_DIR.exists()

        # Check for chat history files
        chat_files = []
        for chat_path in self.CHAT_HISTORY_PATHS:
            if chat_path.exists():
                chat_files.extend(chat_path.rglob("*.json"))
                chat_files.extend(chat_path.rglob("*.md"))
                chat_files.extend(chat_path.rglob("*chat*"))
        stats["potential_chat_files"] = len(chat_files)

        return stats

    def _is_cloud_model(self, model: Dict) -> bool:
        """Detect if a model is cloud-hosted."""
        name = model.get("name", "")
        # Cloud models have :cloud suffix or remote_host field
        if ":cloud" in name:
            return True
        if model.get("remote_host") or model.get("remote_model"):
            return True
        # Check if model is tiny (just a proxy) vs full local model
        size = model.get("size", 0)
        if size and size < 1000000:  # Less than 1MB suggests cloud proxy
            return True
        return False

    def _is_excluded_model(self, model: Dict) -> bool:
        """Check if model should be excluded (not coding-focused)."""
        name = model.get("name", "").lower()
        family = model.get("details", {}).get("family", "").lower()
        return any(excluded in name for excluded in self.EXCLUDED_MODELS) or \
               any(excluded in family for excluded in self.EXCLUDED_MODELS)

    def _is_coding_model(self, model: Dict) -> bool:
        """Check if model is coding-capable and consumer-hardware friendly."""
        name = model.get("name", "").lower()
        family = model.get("details", {}).get("family", "").lower()
        return any(coding in name or coding in family for coding in self.CODING_MODELS)

    def _filter_models(self, models: List[Dict]) -> List[Dict]:
        """Filter to relevant coding models, excluding non-coding ones."""
        return [m for m in models if not self._is_excluded_model(m)]

    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        """Extract Ollama model activity sessions.

        Returns list of session dicts:
        {
            "tool": "ollama",
            "session_id": str,
            "started_at": str,
            "ended_at": str,
            "summary": str,
            "tags": list,
            "raw_content": str,
            "turns": [
                {
                    "role": "user" | "assistant" | "system",
                    "content": str,
                    "timestamp": str,
                    "model": str (optional)
                }
            ]
        }
        """
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {stats.get('relevant_models', 0)} relevant models ({stats.get('coding_models', 0)} coding, {stats.get('local_models', 0)} local, {stats.get('cloud_models', 0)} cloud). Excluded: {', '.join(stats.get('excluded_names', []))}",
                "tags": ["dry-run", "ollama", "models", "coding"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]

        sessions = []

        # Extract model inventory as a session
        if self.models:
            sessions.append(self._create_model_inventory_session())

        # Look for actual chat history files
        for chat_path in self.CHAT_HISTORY_PATHS:
            if chat_path.exists():
                try:
                    sessions.extend(self._extract_chat_history(chat_path, limit))
                except Exception as e:
                    print(f"  Warning: Could not read Ollama chat history from {chat_path}: {e}")

        # Check for Ollama command history
        history_file = self.OLLAMA_DIR / "history"
        if history_file.exists():
            try:
                sessions.append(self._parse_shell_history(history_file))
            except Exception as e:
                print(f"  Warning: Could not read Ollama history: {e}")

        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)

    def _create_model_inventory_session(self) -> Dict:
        """Create a session from the filtered model inventory."""
        now = datetime.now().isoformat()

        filtered = self._filter_models(self.models)
        local_models = []
        cloud_models = []
        coding_local = []

        for model in filtered:
            info = {
                "name": model.get("name"),
                "family": model.get("details", {}).get("family"),
                "parameters": model.get("details", {}).get("parameter_size"),
                "quantization": model.get("details", {}).get("quantization_level"),
                "size_mb": round(model.get("size", 0) / (1024 * 1024), 2) if model.get("size") else None,
                "coding": self._is_coding_model(model),
            }
            if self._is_cloud_model(model):
                info["remote_host"] = model.get("remote_host", "ollama.com")
                cloud_models.append(info)
            else:
                local_models.append(info)
                if info["coding"]:
                    coding_local.append(info)

        excluded = [m.get("name") for m in self.models if self._is_excluded_model(m)]

        content = f"Ollama Coding Model Inventory\n\n"
        content += f"Consumer-Hardware Coding Models ({len(coding_local)} local):\n"
        for m in coding_local:
            content += f"  - {m['name']} ({m['parameters']}, {m['quantization']}, {m['size_mb']} MB)\n"

        if len(local_models) > len(coding_local):
            content += f"\nOther Local Models ({len(local_models) - len(coding_local)}):\n"
            for m in local_models:
                if not m["coding"]:
                    content += f"  - {m['name']} ({m['parameters']}, {m['quantization']})\n"

        if cloud_models:
            content += f"\nCloud Models ({len(cloud_models)}):\n"
            for m in cloud_models:
                content += f"  - {m['name']} → {m['remote_host']}\n"

        if excluded:
            content += f"\nExcluded (not coding-focused): {', '.join(excluded)}\n"

        return {
            "tool": self.TOOL_NAME,
            "session_id": f"ollama_inventory_{datetime.now().strftime('%Y%m%d')}",
            "started_at": now,
            "ended_at": now,
            "summary": f"Ollama: {len(coding_local)} coding models on consumer hardware, {len(cloud_models)} cloud. Excluded: {len(excluded)}",
            "tags": ["ollama", "models", "inventory", "coding"] + [m.get("name", "") for m in filtered][:5],
            "raw_content": json.dumps({"local": local_models, "cloud": cloud_models, "excluded": excluded}),
            "turns": [
                {
                    "role": "system",
                    "content": content,
                    "timestamp": now
                }
            ]
        }

    def _extract_chat_history(self, chat_path: Path, limit: Optional[int] = None) -> List[Dict]:
        """Look for and extract chat history files from Ollama clients."""
        sessions = []

        # Look for JSON chat exports
        for json_file in chat_path.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                if self._looks_like_chat(data):
                    session = self._parse_chat_json(data, json_file.name)
                    if session:
                        sessions.append(session)
            except (json.JSONDecodeError, Exception):
                continue

        # Look for markdown chat exports
        for md_file in chat_path.rglob("*.md"):
            try:
                content = md_file.read_text()
                if "ollama" in content.lower() or "model" in content.lower():
                    session = self._parse_chat_markdown(content, md_file.name)
                    if session:
                        sessions.append(session)
            except Exception:
                continue

        return sessions[:limit] if limit else sessions

    def _looks_like_chat(self, data) -> bool:
        """Heuristic to check if JSON data looks like a chat."""
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                return any(k in first for k in ["role", "message", "content", "user", "assistant"])
        elif isinstance(data, dict):
            return any(k in data for k in ["messages", "conversation", "chat", "turns"])
        return False

    def _parse_chat_json(self, data, filename: str) -> Optional[Dict]:
        """Parse a JSON chat export into a session."""
        turns = []

        if isinstance(data, list):
            for msg in data:
                if isinstance(msg, dict):
                    turns.append({
                        "role": msg.get("role") or msg.get("sender") or "unknown",
                        "content": msg.get("content") or msg.get("message") or msg.get("text") or "",
                        "timestamp": msg.get("timestamp") or msg.get("created_at") or datetime.now().isoformat(),
                        "model": msg.get("model")
                    })
        elif isinstance(data, dict):
            messages = data.get("messages", []) or data.get("conversation", [])
            for msg in messages:
                if isinstance(msg, dict):
                    turns.append({
                        "role": msg.get("role") or "unknown",
                        "content": msg.get("content") or "",
                        "timestamp": msg.get("timestamp") or datetime.now().isoformat(),
                        "model": msg.get("model")
                    })

        if not turns:
            return None

        return {
            "tool": self.TOOL_NAME,
            "session_id": f"ollama_chat_{filename.replace('.json', '')}",
            "started_at": turns[0].get("timestamp"),
            "ended_at": turns[-1].get("timestamp"),
            "summary": self._generate_summary(turns),
            "tags": ["ollama", "chat", "conversation"],
            "raw_content": json.dumps(turns),
            "turns": turns
        }

    def _parse_chat_markdown(self, content: str, filename: str) -> Optional[Dict]:
        """Parse a markdown chat export."""
        now = datetime.now().isoformat()

        # Simple heuristic: split by common role markers
        turns = []
        lines = content.split("\n")
        current_role = "system"
        current_content = []

        for line in lines:
            if re.match(r'^#{1,3}\s*(User|Human|You|Assistant|Bot|Model)', line, re.I):
                if current_content:
                    turns.append({
                        "role": current_role,
                        "content": "\n".join(current_content).strip(),
                        "timestamp": now
                    })
                current_role = "user" if any(w in line.lower() for w in ["user", "human", "you"]) else "assistant"
                current_content = []
            elif re.match(r'^\*\*(User|Human|You|Assistant|Bot|Model)\*\*', line, re.I):
                if current_content:
                    turns.append({
                        "role": current_role,
                        "content": "\n".join(current_content).strip(),
                        "timestamp": now
                    })
                current_role = "user" if any(w in line.lower() for w in ["user", "human", "you"]) else "assistant"
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            turns.append({
                "role": current_role,
                "content": "\n".join(current_content).strip(),
                "timestamp": now
            })

        if len(turns) < 2:
            return None

        return {
            "tool": self.TOOL_NAME,
            "session_id": f"ollama_md_{filename.replace('.md', '')}",
            "started_at": now,
            "ended_at": now,
            "summary": self._generate_summary(turns),
            "tags": ["ollama", "chat", "markdown"],
            "raw_content": content,
            "turns": turns
        }

    def _parse_shell_history(self, history_file: Path) -> Dict:
        """Parse Ollama shell command history."""
        now = datetime.now().isoformat()
        content = history_file.read_text()
        lines = [l.strip() for l in content.split("\n") if l.strip()]

        # Extract model usage patterns
        models_used = set()
        for line in lines:
            match = re.search(r'ollama\s+(run|pull)\s+(\S+)', line)
            if match:
                models_used.add(match.group(2))

        turns = [
            {
                "role": "system",
                "content": f"Ollama command history ({len(lines)} commands). Models used: {', '.join(models_used) or 'none detected'}",
                "timestamp": now
            }
        ]

        return {
            "tool": self.TOOL_NAME,
            "session_id": f"ollama_history_{datetime.now().strftime('%Y%m%d')}",
            "started_at": now,
            "ended_at": now,
            "summary": f"Ollama shell history: {len(models_used)} models, {len(lines)} commands",
            "tags": ["ollama", "history", "commands"] + list(models_used),
            "raw_content": "\n".join(lines),
            "turns": turns
        }

    def _generate_summary(self, turns: List[Dict]) -> str:
        """Generate a one-line summary from conversation turns."""
        user_messages = [t["content"] for t in turns if t.get("role") in ("user", "human")]
        if user_messages:
            first_msg = user_messages[0]
            summary = first_msg.split('.')[0][:100]
            return summary + "..." if len(first_msg) > 100 else summary
        return "Ollama chat session"
