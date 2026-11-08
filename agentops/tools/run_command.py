"""
Safe terminal command execution tool with approval enforcement, timeout,
output limits, secret masking, and cancellation support.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from agentops.tools.base import BaseTool
from agentops.security.approvals import ApprovalManager
from agentops.security.secrets import mask_secrets


class RunCommandTool(BaseTool):
    name: str = "run_command"
    description: str = "Runs a shell or terminal command in the workspace directory with explicit user approval."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact command string to execute",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Optional timeout in seconds (default: 30.0)",
            },
        },
        "required": ["command"],
    }

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        approval_manager: Optional[ApprovalManager] = None,
        default_timeout_seconds: float = 30.0,
        max_output_bytes: int = 50_000,
    ):
        self.workspace_root = workspace_root or Path.cwd()
        self.approval_manager = approval_manager or ApprovalManager()
        self.default_timeout_seconds = default_timeout_seconds
        self.max_output_bytes = max_output_bytes

    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        command = arguments.get("command")
        if not command:
            return {"error": "Missing required argument 'command'"}

        timeout = float(arguments.get("timeout_seconds") or self.default_timeout_seconds)
        ws = (context.get("workspace_root") if context else None) or self.workspace_root
        approval_mgr = (context.get("approval_manager") if context else None) or self.approval_manager

        # Explicit approval required
        details = {
            "command": command,
            "cwd": str(ws),
            "timeout_seconds": timeout,
        }
        approved = approval_mgr.request_approval("run_command", details)
        if not approved:
            return {
                "command": command,
                "error": "Command execution cancelled: user declined or permission denied.",
                "approved": False,
            }

        # Platform-specific shell
        is_windows = sys.platform == "win32"
        shell_cmd = command

        try:
            if is_windows:
                # Use powershell on Windows
                process = await asyncio.create_subprocess_exec(
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    shell_cmd,
                    cwd=str(ws),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "/bin/sh",
                    "-c",
                    shell_cmd,
                    cwd=str(ws),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                return {
                    "command": command,
                    "error": f"Command timed out after {timeout} seconds",
                    "timed_out": True,
                    "exit_code": -1,
                }

            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")

            # Truncate output if exceeding maximum bytes
            if len(stdout_str) > self.max_output_bytes:
                stdout_str = stdout_str[:self.max_output_bytes] + "\n... [OUTPUT TRUNCATED] ..."
            if len(stderr_str) > self.max_output_bytes:
                stderr_str = stderr_str[:self.max_output_bytes] + "\n... [OUTPUT TRUNCATED] ..."

            # Mask credentials/secrets in output
            clean_stdout = mask_secrets(stdout_str)
            clean_stderr = mask_secrets(stderr_str)

            return {
                "command": command,
                "exit_code": process.returncode,
                "stdout": clean_stdout,
                "stderr": clean_stderr,
                "success": process.returncode == 0,
            }
        except Exception as e:
            return {"command": command, "error": f"Failed to execute command: {e}"}

