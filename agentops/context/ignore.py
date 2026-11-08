"""
Gitignore-compatible file pattern matcher.
"""

import fnmatch
from pathlib import Path
from typing import List, Union, Optional


DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".git/*",
    ".svn",
    ".hg",
    "node_modules",
    "node_modules/*",
    "__pycache__",
    "__pycache__/*",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    "env",
    "env/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.lock",
    "bun.lock",
    "*.min.js",
    "*.map",
    ".agentops",
    ".agentops/*",
    ".openclaude-profile.json",
    ".agentops-profile.json",
]


class IgnoreFilter:
    def __init__(self, workspace_root: Union[str, Path], custom_patterns: Optional[List[str]] = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.patterns: List[str] = list(DEFAULT_IGNORE_PATTERNS)
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        gitignore_path = self.workspace_root / ".gitignore"
        if gitignore_path.is_file():
            try:
                for line in gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    self.patterns.append(line)
            except Exception:
                pass

    def is_ignored(self, path: Union[str, Path]) -> bool:
        """Returns True if the path should be ignored."""
        p = Path(path)
        if p.is_absolute():
            try:
                rel_path = p.resolve().relative_to(self.workspace_root)
            except ValueError:
                return True
        else:
            rel_path = p

        rel_str = str(rel_path).replace("\\", "/")
        parts = rel_str.split("/")

        # Check part-by-part and full path against ignore patterns
        for pattern in self.patterns:
            clean_pattern = pattern.strip().replace("\\", "/")
            if clean_pattern.endswith("/"):
                clean_pattern = clean_pattern[:-1]

            # Direct match
            if fnmatch.fnmatch(rel_str, clean_pattern):
                return True
            if fnmatch.fnmatch(rel_str, f"*/{clean_pattern}*"):
                return True

            # Match against each individual path component
            for part in parts:
                if fnmatch.fnmatch(part, clean_pattern):
                    return True

        return False
