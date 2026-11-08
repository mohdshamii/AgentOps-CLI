"""
Repository workspace indexer for discovering relevant code files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Union, Optional
from agentops.context.ignore import IgnoreFilter


@dataclass
class IndexedFile:
    path: Path
    relative_path: str
    size_bytes: int
    is_binary: bool = False
    estimated_tokens: int = 0


def is_binary_file(file_path: Path) -> bool:
    """Checks if a file contains null bytes within the first 1024 bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return True


class RepositoryIndexer:
    def __init__(
        self,
        workspace_root: Union[str, Path],
        max_file_size_bytes: int = 500_000,
        custom_ignore_patterns: Optional[List[str]] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.max_file_size_bytes = max_file_size_bytes
        self.ignore_filter = IgnoreFilter(self.workspace_root, custom_patterns=custom_ignore_patterns)

    def scan_files(self) -> List[IndexedFile]:
        """Scans the repository and returns indexed, non-ignored files."""
        indexed: List[IndexedFile] = []

        for root, dirs, files in os_walk_filtered(self.workspace_root, self.ignore_filter):
            for file_name in files:
                file_path = Path(root) / file_name
                rel_path = str(file_path.relative_to(self.workspace_root)).replace("\\", "/")

                if self.ignore_filter.is_ignored(rel_path):
                    continue

                try:
                    stat = file_path.stat()
                    size = stat.st_size

                    # Skip empty or oversized files
                    if size == 0 or size > self.max_file_size_bytes:
                        continue

                    binary = is_binary_file(file_path)
                    if binary:
                        continue

                    tokens = max(1, size // 4)
                    indexed.append(
                        IndexedFile(
                            path=file_path,
                            relative_path=rel_path,
                            size_bytes=size,
                            is_binary=False,
                            estimated_tokens=tokens,
                        )
                    )
                except Exception:
                    continue

        return indexed


def os_walk_filtered(root_dir: Path, ignore_filter: IgnoreFilter):
    """Walks directory tree, pruning ignored subdirectories early for high performance."""
    import os
    for root, dirs, files in os.walk(root_dir):
        # Prune dirs in-place
        dirs[:] = [
            d for d in dirs
            if not ignore_filter.is_ignored(Path(root) / d)
        ]
        yield root, dirs, files

