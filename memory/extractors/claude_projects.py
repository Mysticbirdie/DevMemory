"""Extractor for Claude.ai Projects, Artifacts, and Canvas.

Claude Web has three advanced features that store data outside normal chat:
- **Projects** — Persistent projects with uploaded files
- **Artifacts** — Interactive code/design blocks (HTML, React, etc.)
- **Canvas** — Visual collaborative workspace

These require manual export from Claude Web, then import into DevMemory.

Export from Claude Web:
1. Projects: Share button → "Export project" → downloads ZIP
2. Artifacts: Click artifact → Download button (or "View source")
3. Canvas: Share → "Export as Markdown"

Save exports to:
    ~/Downloads/Claude/Projects/
    ~/Downloads/Claude/Artifacts/
    ~/Downloads/Claude/Canvas/

Then run:
    python3 cli.py import-claude-projects --all
    python3 cli.py import-claude-artifacts --all
    python3 cli.py import-claude-canvas --all
"""

import json
import zipfile
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class ClaudeProjectsExtractor(BaseExtractor):
    """Extracts Claude.ai Project exports.
    
    Claude Projects are persistent workspaces with:
    - Uploaded files (code, docs, data)
    - Multiple conversations within the project
    - Custom instructions
    """
    
    TOOL_NAME = "claude_projects"
    DISPLAY_NAME = "Claude Projects"
    
    # Default import directories
    IMPORT_DIRS = {
        "projects": Path.home() / "Downloads" / "Claude" / "Projects",
        "artifacts": Path.home() / "Downloads" / "Claude" / "Artifacts", 
        "canvas": Path.home() / "Downloads" / "Claude" / "Canvas",
    }
    
    def __init__(self, import_dir: Optional[Path] = None):
        self.import_dir = import_dir or self.IMPORT_DIRS["projects"]
    
    def is_available(self) -> bool:
        """Check if Claude Project exports exist."""
        return self.import_dir.exists() and any(self.import_dir.iterdir())
    
    def get_stats(self) -> Dict:
        """Return statistics about available project exports."""
        stats = super().get_stats()
        
        if self.import_dir.exists():
            # Count ZIP files (project exports)
            zip_files = list(self.import_dir.glob("*.zip"))
            stats["project_exports"] = len(zip_files)
            
            # Count extracted folders
            folders = [d for d in self.import_dir.iterdir() if d.is_dir()]
            stats["extracted_projects"] = len(folders)
            
            # List project names
            stats["projects"] = [f.name for f in folders + zip_files]
        
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        """Extract sessions from Claude Project exports.
        
        Project exports contain:
        - project.json (metadata)
        - conversations/ (chat history)
        - files/ (uploaded files)
        - instructions.md (custom instructions)
        """
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {stats.get('project_exports', 0)} project exports available",
                "tags": ["dry-run", "claude-web", "projects"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        if not self.import_dir.exists():
            return sessions
        
        # Process ZIP exports
        for zip_file in self.import_dir.glob("*.zip"):
            try:
                session = self._parse_project_zip(zip_file)
                if session:
                    sessions.append(session)
            except Exception as e:
                print(f"  Warning: Could not parse project ZIP {zip_file.name}: {e}")
        
        # Process extracted folders
        for project_dir in self.import_dir.iterdir():
            if project_dir.is_dir():
                try:
                    session = self._parse_project_folder(project_dir)
                    if session:
                        sessions.append(session)
                except Exception as e:
                    print(f"  Warning: Could not parse project folder {project_dir.name}: {e}")
        
        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)
    
    def _parse_project_zip(self, zip_path: Path) -> Optional[Dict]:
        """Parse a Claude Project ZIP export."""
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Look for project metadata
            project_info = {}
            conversations = []
            files = []
            
            for name in zf.namelist():
                if name.endswith('project.json'):
                    try:
                        project_info = json.loads(zf.read(name))
                    except:
                        pass
                elif 'conversation' in name.lower() and name.endswith('.json'):
                    try:
                        conv = json.loads(zf.read(name))
                        conversations.append(conv)
                    except:
                        pass
                elif name.startswith('files/'):
                    files.append(name)
            
            # Build session from project data
            turns = []
            for conv in conversations[:5]:  # Limit conversations
                if isinstance(conv, dict) and 'messages' in conv:
                    for msg in conv['messages'][:20]:  # Limit messages per conv
                        turns.append({
                            "role": msg.get("role", "unknown"),
                            "content": msg.get("content", "")[:2000],
                            "timestamp": msg.get("timestamp", datetime.now().isoformat())
                        })
            
            if not turns:
                # Create synthetic session from project info
                turns.append({
                    "role": "system",
                    "content": f"Claude Project: {project_info.get('name', zip_path.stem)}\n\nFiles: {', '.join(files[:10])}",
                    "timestamp": datetime.now().isoformat()
                })
            
            return {
                "tool": self.TOOL_NAME,
                "session_id": f"claude_project_{zip_path.stem}",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Claude Project: {project_info.get('name', zip_path.stem)}",
                "tags": ["claude-web", "projects", "files"] + [f"ext:{Path(f).suffix}" for f in files[:5]],
                "raw_content": json.dumps({"project": project_info, "files": files}),
                "turns": turns
            }
    
    def _parse_project_folder(self, project_dir: Path) -> Optional[Dict]:
        """Parse an extracted Claude Project folder."""
        # Look for project metadata
        project_info = {}
        meta_file = project_dir / "project.json"
        if meta_file.exists():
            try:
                project_info = json.loads(meta_file.read_text())
            except:
                pass
        
        # Find conversations
        conversations = []
        conv_dir = project_dir / "conversations"
        if conv_dir.exists():
            for conv_file in conv_dir.glob("*.json"):
                try:
                    conv = json.loads(conv_file.read_text())
                    conversations.append(conv)
                except:
                    continue
        
        # Find files
        files_dir = project_dir / "files"
        files = []
        if files_dir.exists():
            files = [str(f.relative_to(project_dir)) for f in files_dir.rglob("*") if f.is_file()]
        
        # Build turns from conversations
        turns = []
        for conv in conversations[:5]:
            if isinstance(conv, dict) and 'messages' in conv:
                for msg in conv['messages'][:20]:
                    turns.append({
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", "")[:2000],
                        "timestamp": msg.get("timestamp", datetime.now().isoformat())
                    })
        
        if not turns:
            turns.append({
                "role": "system",
                "content": f"Claude Project: {project_info.get('name', project_dir.name)}\nFiles: {len(files)}",
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "tool": self.TOOL_NAME,
            "session_id": f"claude_project_{project_dir.name}",
            "started_at": datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "summary": f"Claude Project: {project_info.get('name', project_dir.name)}",
            "tags": ["claude-web", "projects", "files"],
            "raw_content": json.dumps({"project": project_info, "files": files[:20]}),
            "turns": turns
        }


class ClaudeArtifactsExtractor(BaseExtractor):
    """Extracts Claude Artifacts (designs, code blocks, interactive components).
    
    Artifacts are exported from Claude Web:
    1. Click artifact → "View source" or Download
    2. Save to ~/Downloads/Claude/Artifacts/
    """
    
    TOOL_NAME = "claude_artifacts"
    DISPLAY_NAME = "Claude Artifacts"
    
    ARTIFACTS_DIR = Path.home() / "Downloads" / "Claude" / "Artifacts"
    
    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = artifacts_dir or self.ARTIFACTS_DIR
    
    def is_available(self) -> bool:
        return self.artifacts_dir.exists() and any(self.artifacts_dir.iterdir())
    
    def get_stats(self) -> Dict:
        stats = super().get_stats()
        if self.artifacts_dir.exists():
            # Count by file type
            html_count = len(list(self.artifacts_dir.glob("*.html")))
            jsx_count = len(list(self.artifacts_dir.glob("*.jsx")))
            tsx_count = len(list(self.artifacts_dir.glob("*.tsx")))
            py_count = len(list(self.artifacts_dir.glob("*.py")))
            
            stats["html_artifacts"] = html_count
            stats["jsx_artifacts"] = jsx_count
            stats["tsx_artifacts"] = tsx_count
            stats["python_artifacts"] = py_count
            stats["total_artifacts"] = html_count + jsx_count + tsx_count + py_count
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {stats.get('total_artifacts', 0)} artifacts available",
                "tags": ["dry-run", "claude-web", "artifacts"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        if not self.artifacts_dir.exists():
            return sessions
        
        # Process artifact files by type
        artifact_patterns = ["*.html", "*.jsx", "*.tsx", "*.py", "*.css", "*.js"]
        
        for pattern in artifact_patterns:
            for artifact_file in self.artifacts_dir.glob(pattern):
                try:
                    session = self._parse_artifact_file(artifact_file)
                    if session:
                        sessions.append(session)
                except Exception as e:
                    print(f"  Warning: Could not parse artifact {artifact_file.name}: {e}")
        
        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)
    
    def _parse_artifact_file(self, artifact_path: Path) -> Optional[Dict]:
        """Parse a single artifact file."""
        content = artifact_path.read_text(errors='ignore')
        
        # Extract title/description from content
        title = artifact_path.stem
        
        # Try to extract from HTML title tag
        if artifact_path.suffix == '.html':
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
        
        # Detect artifact type
        artifact_type = "code"
        if artifact_path.suffix in ['.html', '.jsx', '.tsx']:
            if "<svg" in content or "react" in content.lower():
                artifact_type = "design"
            else:
                artifact_type = "web-component"
        elif artifact_path.suffix == '.py':
            artifact_type = "python-script"
        
        # Get file stats
        file_size = artifact_path.stat().st_size
        line_count = len(content.split('\n'))
        
        return {
            "tool": self.TOOL_NAME,
            "session_id": f"claude_artifact_{artifact_path.stem}",
            "started_at": datetime.fromtimestamp(artifact_path.stat().st_mtime).isoformat(),
            "ended_at": datetime.fromtimestamp(artifact_path.stat().st_mtime).isoformat(),
            "summary": f"Artifact: {title} ({artifact_path.suffix})",
            "tags": ["claude-web", "artifacts", artifact_type, artifact_path.suffix.lstrip('.')],
            "raw_content": content[:5000],  # Limit raw content
            "turns": [
                {
                    "role": "assistant",
                    "content": f"Created artifact: {title}\nType: {artifact_type}\nSize: {file_size} bytes, {line_count} lines\n\n```\n{content[:2000]}\n```",
                    "timestamp": datetime.fromtimestamp(artifact_path.stat().st_mtime).isoformat()
                }
            ],
            "artifact_meta": {
                "file_name": artifact_path.name,
                "file_type": artifact_path.suffix,
                "file_size": file_size,
                "line_count": line_count,
                "artifact_type": artifact_type
            }
        }


class ClaudeCanvasExtractor(BaseExtractor):
    """Extracts Claude Canvas exports.
    
    Canvas is Claude's visual collaborative workspace.
    Export: Share → "Export as Markdown" → save to ~/Downloads/Claude/Canvas/
    """
    
    TOOL_NAME = "claude_canvas"
    DISPLAY_NAME = "Claude Canvas"
    
    CANVAS_DIR = Path.home() / "Downloads" / "Claude" / "Canvas"
    
    def __init__(self, canvas_dir: Optional[Path] = None):
        self.canvas_dir = canvas_dir or self.CANVAS_DIR
    
    def is_available(self) -> bool:
        return self.canvas_dir.exists() and any(self.canvas_dir.iterdir())
    
    def get_stats(self) -> Dict:
        stats = super().get_stats()
        if self.canvas_dir.exists():
            md_files = len(list(self.canvas_dir.glob("*.md")))
            stats["canvas_exports"] = md_files
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False) -> List[Dict]:
        if dry_run:
            stats = self.get_stats()
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {stats.get('canvas_exports', 0)} canvas exports available",
                "tags": ["dry-run", "claude-web", "canvas"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        if not self.canvas_dir.exists():
            return sessions
        
        for canvas_file in self.canvas_dir.glob("*.md"):
            try:
                session = self._parse_canvas_file(canvas_file)
                if session:
                    sessions.append(session)
            except Exception as e:
                print(f"  Warning: Could not parse canvas {canvas_file.name}: {e}")
        
        return self.filter_valid_sessions(sessions[:limit] if limit else sessions)
    
    def _parse_canvas_file(self, canvas_path: Path) -> Optional[Dict]:
        """Parse a Claude Canvas markdown export."""
        content = canvas_path.read_text(errors='ignore')
        
        # Extract title from first heading
        title = canvas_path.stem
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1)
        
        # Count sections (headings)
        sections = re.findall(r'^#{1,3} .+$', content, re.MULTILINE)
        
        # Detect content types
        has_code = '```' in content
        has_tables = '|' in content and '\n|' in content
        has_images = '![' in content
        
        return {
            "tool": self.TOOL_NAME,
            "session_id": f"claude_canvas_{canvas_path.stem}",
            "started_at": datetime.fromtimestamp(canvas_path.stat().st_mtime).isoformat(),
            "ended_at": datetime.fromtimestamp(canvas_path.stat().st_mtime).isoformat(),
            "summary": f"Canvas: {title} ({len(sections)} sections)",
            "tags": ["claude-web", "canvas"] + 
                     (["code"] if has_code else []) + 
                     (["tables"] if has_tables else []) + 
                     (["images"] if has_images else []),
            "raw_content": content[:5000],
            "turns": [
                {
                    "role": "assistant",
                    "content": f"Canvas workspace: {title}\nSections: {len(sections)}\n\n{content[:2000]}",
                    "timestamp": datetime.fromtimestamp(canvas_path.stat().st_mtime).isoformat()
                }
            ],
            "canvas_meta": {
                "file_name": canvas_path.name,
                "sections": len(sections),
                "has_code": has_code,
                "has_tables": has_tables,
                "has_images": has_images
            }
        }
