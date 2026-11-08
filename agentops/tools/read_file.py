"""
Safe file reading tool with workspace path traversal protection and size limits.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from agentops.tools.base import BaseTool
from agentops.security.paths import resolve_safe_path, PathSecurityError


class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Read contents of a file within the workspace safely."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file within the workspace",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-based start line to read",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-based end line to read (inclusive)",
            },
        },
        "required": ["path"],
    }

    def __init__(self, workspace_root: Optional[Path] = None, max_bytes: int = 500_000):
        self.workspace_root = workspace_root or Path.cwd()
        self.max_bytes = max_bytes

    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        target_path_str = arguments.get("path")
        if not target_path_str:
            return {"error": "Missing required argument 'path'"}

        ws = (context.get("workspace_root") if context else None) or self.workspace_root

        try:
            safe_path = resolve_safe_path(target_path_str, ws)
        except PathSecurityError as e:
            return {"error": str(e), "path": target_path_str}

        if not safe_path.exists():
            return {"error": f"File '{target_path_str}' does not exist", "path": target_path_str}

        if safe_path.is_dir():
            return {"error": f"Path '{target_path_str}' is a directory, not a file", "path": target_path_str}

        try:
            stat = safe_path.stat()
            if stat.st_size > self.max_bytes:
                return {
                    "error": f"File exceeds maximum size limit of {self.max_bytes} bytes (size: {stat.st_size} bytes)",
                    "path": target_path_str,
                }

            content = safe_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)

            start = arguments.get("start_line")
            end = arguments.get("end_line")

            if start is not None or end is not None:
                s_idx = max(0, (start - 1)) if start is not None else 0
                e_idx = end if end is not None else len(lines)
                sliced_content = "".join(lines[s_idx:e_idx])
                return {
                    "path": target_path_str,
                    "content": sliced_content,
                    "total_lines": len(lines),
                    "start_line": s_idx + 1,
                    "end_line": min(e_idx, len(lines)),
                }

            return {
                "path": target_path_str,
                "content": content,
                "total_lines": len(lines),
            }
        except Exception as e:
            return {"error": f"Failed to read file: {e}", "path": target_path_str}

