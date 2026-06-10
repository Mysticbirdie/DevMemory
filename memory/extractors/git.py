"""Extractor for Git activity.

Reads commit history, file changes, and diffs from Git repositories.
"""

import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .base import BaseExtractor


class GitExtractor(BaseExtractor):
    """Extracts activity from Git repositories."""
    
    TOOL_NAME = "git"
    DISPLAY_NAME = "Git"
    
    def __init__(self, repo_paths: Optional[List[Path]] = None):
        """Initialize with repo paths. Defaults to current directory."""
        self.repo_paths = repo_paths or [Path.cwd()]
        self.sessions: List[Dict] = []
    
    def is_available(self) -> bool:
        """Check if git is available and repos exist."""
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            return any((repo / ".git").exists() for repo in self.repo_paths)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_stats(self) -> Dict:
        """Return statistics about available Git data."""
        stats = super().get_stats()
        
        repo_stats = []
        for repo in self.repo_paths:
            if not (repo / ".git").exists():
                continue
            
            try:
                # Count commits in last 30 days
                result = subprocess.run(
                    ["git", "-C", str(repo), "rev-list", "--count", "--since=30 days ago", "HEAD"],
                    capture_output=True, text=True, check=True
                )
                commit_count = int(result.stdout.strip())
                
                # Get repo name
                repo_name = repo.name
                
                repo_stats.append({
                    "name": repo_name,
                    "path": str(repo),
                    "recent_commits": commit_count
                })
            except (subprocess.CalledProcessError, ValueError):
                continue
        
        stats["repos"] = repo_stats
        stats["repo_count"] = len(repo_stats)
        return stats
    
    def extract(self, limit: Optional[int] = None, dry_run: bool = False, since: Optional[str] = None) -> List[Dict]:
        """Extract commits as sessions.
        
        Args:
            limit: Max sessions to extract
            dry_run: If True, return preview stats without full session data
            since: Git --since parameter (e.g. "30 days ago")
            
        Returns list of session dicts with format:
        {
            "tool": "git",
            "session_id": str (commit hash),
            "started_at": str,
            "ended_at": str,
            "summary": str (commit message),
            "tags": list,
            "raw_content": str (diff),
            "turns": [
                {
                    "role": "developer",
                    "content": str,
                    "timestamp": str
                }
            ]
        }
        """
        if dry_run:
            stats = self.get_stats()
            total_commits = sum(r.get("recent_commits", 0) for r in stats.get("repos", []))
            return [{
                "tool": self.TOOL_NAME,
                "session_id": f"{self.TOOL_NAME}_dry_run",
                "started_at": datetime.now().isoformat(),
                "ended_at": datetime.now().isoformat(),
                "summary": f"Dry run: {total_commits} recent commits across {stats.get('repo_count', 0)} repos",
                "tags": ["dry-run"],
                "raw_content": json.dumps(stats),
                "turns": []
            }]
        
        sessions = []
        
        for repo in self.repo_paths:
            if not (repo / ".git").exists():
                continue
            
            try:
                sessions.extend(self._extract_from_repo(repo, limit, since))
            except Exception as e:
                print(f"  Warning: Could not extract from {repo}: {e}")
        
        # Validate and filter (Git commits are single-turn, so skip validation)
        return sessions[:limit] if limit else sessions
    
    def _extract_from_repo(self, repo: Path, limit: Optional[int], since: Optional[str]) -> List[Dict]:
        """Extract commits from a single repository."""
        sessions = []
        
        # Build git log command
        cmd = [
            "git", "-C", str(repo),
            "log",
            "--format=%H|%ci|%s|%b|%an",
            "--numstat",
            "--no-merges"
        ]
        
        if since:
            cmd.extend(["--since", since])
        
        if limit:
            cmd.extend(["-n", str(limit)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            commits = self._parse_git_log(result.stdout, str(repo))
            sessions.extend(commits)
        except subprocess.CalledProcessError as e:
            print(f"Warning: git log failed for {repo}: {e}")
        
        return sessions
    
    def _parse_git_log(self, log_output: str, repo_path: str) -> List[Dict]:
        """Parse git log output into session structures."""
        sessions = []
        
        # Split by commit
        commit_blocks = log_output.split('\n\n')
        
        for block in commit_blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split('\n')
            if not lines:
                continue
            
            # Parse header line: hash|date|subject|body|author
            header = lines[0].split('|', 4)
            if len(header) < 3:
                continue
            
            commit_hash = header[0]
            timestamp = header[1]
            subject = header[2]
            body = header[3] if len(header) > 3 else ""
            author = header[4] if len(header) > 4 else ""
            
            # Parse file stats (remaining lines)
            files = []
            lines_added = 0
            lines_deleted = 0
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) == 3:
                    try:
                        added = int(parts[0]) if parts[0] != '-' else 0
                        deleted = int(parts[1]) if parts[1] != '-' else 0
                        filename = parts[2]
                        lines_added += added
                        lines_deleted += deleted
                        files.append({
                            "path": filename,
                            "added": added,
                            "deleted": deleted
                        })
                    except ValueError:
                        continue
            
            # Create session from commit
            full_message = f"{subject}\n\n{body}".strip()
            
            sessions.append({
                "tool": "git",
                "session_id": commit_hash,
                "started_at": timestamp,
                "ended_at": timestamp,
                "summary": subject,
                "tags": self._extract_tags_from_commit(subject, body, files),
                "raw_content": full_message,
                "turns": [
                    {
                        "role": "developer",
                        "content": full_message,
                        "timestamp": timestamp,
                        "files_changed": files,
                        "lines_added": lines_added,
                        "lines_deleted": lines_deleted,
                        "author": author
                    }
                ]
            })
        
        return sessions
    
    def get_file_history(self, repo: Path, file_path: str, limit: int = 10) -> List[Dict]:
        """Get commit history for a specific file."""
        cmd = [
            "git", "-C", str(repo),
            "log",
            "--format=%H|%ci|%s",
            "--follow",
            "-n", str(limit),
            "--", file_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            history = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    history.append({
                        "commit": parts[0],
                        "timestamp": parts[1],
                        "message": parts[2]
                    })
            return history
        except subprocess.CalledProcessError:
            return []
    
    def get_changed_files(self, repo: Path, since: str = "1 week ago") -> List[str]:
        """Get list of files changed since a given time."""
        cmd = [
            "git", "-C", str(repo),
            "diff",
            "--name-only",
            f"--since={since}"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return [f.strip() for f in result.stdout.split('\n') if f.strip()]
        except subprocess.CalledProcessError:
            return []
    
    def _extract_tags_from_commit(self, subject: str, body: str, files: List[Dict]) -> List[str]:
        """Extract tags from commit message and changed files."""
        text = f"{subject} {body}"
        tags = set()
        
        # Conventional commit types
        conv_types = re.findall(r'^(\w+)(?:\(|!):', subject)
        tags.update(conv_types)
        
        # File extensions
        for f in files:
            ext = Path(f["path"]).suffix
            if ext:
                tags.add(ext.lstrip('.'))
        
        # Technical terms in message
        tech_patterns = [
            r'\b(fix|bug|debug|error|issue)\b',
            r'\b(feat|feature|add|implement|create)\b',
            r'\b(refactor|cleanup|remove|delete)\b',
            r'\b(test|spec|coverage)\b',
            r'\b(docs|readme|documentation)\b',
            r'\b(perf|optimize|speed|fast)\b',
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            tags.update(m.lower() for m in matches)
        
        return list(tags)[:10]
