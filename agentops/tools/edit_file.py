"""
Safe file modification tool with unified diff generation, approval enforcement,
atomic replacement, and concurrent modification protection.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from agentops.tools.base import BaseTool
from agentops.tools.diff import generate_unified_diff
from agentops.security.paths import resolve_safe_path, PathSecurityError
from agentops.security.approvals import ApprovalManager


class EditFileTool(BaseTool):
    name: str = "edit_file"
    description: str = "Proposes and writes changes to a file with unified diff preview and user approval."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the target file within the workspace",
            },
            "new_content": {
                "type": "string",
                "description": "The complete replacement contents of the file",
            },
            "expected_original": {
                "type": "string",
                "description": "Optional original content expected to detect concurrent modifications",
            },
        },
        "required": ["path", "new_content"],
    }

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        approval_manager: Optional[ApprovalManager] = None,
    ):
        self.workspace_root = workspace_root or Path.cwd()
        self.approval_manager = approval_manager or ApprovalManager()

    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        target_path_str = arguments.get("path")
        new_content = arguments.get("new_content")
        expected_original = arguments.get("expected_original")

        if not target_path_str:
            return {"error": "Missing required argument 'path'"}
        if new_content is None:
            return {"error": "Missing required argument 'new_content'"}

        ws = (context.get("workspace_root") if context else None) or self.workspace_root
        approval_mgr = (context.get("approval_manager") if context else None) or self.approval_manager

        try:
            safe_path = resolve_safe_path(target_path_str, ws)
        except PathSecurityError as e:
            return {"error": str(e), "path": target_path_str}

        original_content = ""
        line_ending = "\n"

        if safe_path.exists():
            if safe_path.is_dir():
                return {"error": f"Target '{target_path_str}' is a directory", "path": target_path_str}

            try:
                raw_bytes = safe_path.read_bytes()
                if b"\r\n" in raw_bytes:
                    line_ending = "\r\n"
                original_content = raw_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                return {"error": f"Failed to read existing file: {e}", "path": target_path_str}

            # Concurrent edit detection
            if expected_original is not None:
                # Normalize line endings before comparison
                norm_orig = original_content.replace("\r\n", "\n")
                norm_exp = expected_original.replace("\r\n", "\n")
                if norm_orig != norm_exp:
                    return {
                        "error": "Concurrent modification detected: file content changed on disk since last read",
                        "path": target_path_str,
                        "concurrent_conflict": True,
                    }

        # Normalize line endings to match original
        normalized_new_content = new_content.replace("\r\n", "\n")
        if line_ending == "\r\n":
            normalized_new_content = normalized_new_content.replace("\n", "\r\n")

        diff = generate_unified_diff(original_content, normalized_new_content, file_path=target_path_str)

        if not diff:
            return {
                "path": target_path_str,
                "message": "No changes detected. File is already identical to new_content.",
                "diff": "",
                "applied": False,
            }

        # Request user approval
        details = {
            "path": target_path_str,
            "absolute_path": str(safe_path),
            "diff": diff,
            "new_content": normalized_new_content,
        }
        approved = approval_mgr.request_approval("edit_file", details)
        if not approved:
            return {
                "path": target_path_str,
                "message": "User declined file edit or approval manager rejected modification.",
                "diff": diff,
                "applied": False,
            }

        # Safe atomic write via temporary file
        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_path_str = tempfile.mkstemp(dir=str(safe_path.parent), prefix="tmp_agentops_")
            with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as tmp_file:
                tmp_file.write(normalized_new_content)

            # Atomic replace
            os.replace(tmp_path_str, str(safe_path))

            return {
                "path": target_path_str,
                "applied": True,
                "diff": diff,
                "message": f"Successfully updated '{target_path_str}'",
            }
        except Exception as e:
            if "tmp_path_str" in locals() and os.path.exists(tmp_path_str):
                try:
                    os.unlink(tmp_path_str)
                except Exception:
                    pass
            return {"error": f"Failed to write file: {e}", "path": target_path_str}

