"""
Unit tests for safe agent tools (read_file, edit_file, run_command, diff, registry).
"""

import asyncio
from pathlib import Path
import pytest
from agentops.tools.read_file import ReadFileTool
from agentops.tools.edit_file import EditFileTool
from agentops.tools.run_command import RunCommandTool
from agentops.tools.diff import generate_unified_diff
from agentops.tools.registry import ToolRegistry
from agentops.security.approvals import ApprovalManager, PermissionMode


def test_generate_unified_diff():
    orig = "line 1\nline 2\n"
    new = "line 1\nline two\n"
    diff = generate_unified_diff(orig, new, "test.txt")
    assert "-line 2" in diff
    assert "+line two" in diff


def test_read_file_tool(tmp_path):
    async def _test():
        f = tmp_path / "hello.py"
        f.write_text("line 1\nline 2\nline 3\nline 4\n", encoding="utf-8")

        tool = ReadFileTool(workspace_root=tmp_path)
        res = await tool.execute({"path": "hello.py", "start_line": 2, "end_line": 3})
        assert res["content"] == "line 2\nline 3\n"
        assert res["total_lines"] == 4

        # Outside workspace rejection
        outside_res = await tool.execute({"path": "../outside.txt"})
        assert "error" in outside_res
    asyncio.run(_test())


def test_edit_file_tool_approval_declined(tmp_path):
    async def _test():
        f = tmp_path / "code.py"
        f.write_text("old_code = True\n", encoding="utf-8")

        # Approval manager set to decline
        appr_mgr = ApprovalManager(interactive_prompt_func=lambda a, d: False)
        tool = EditFileTool(workspace_root=tmp_path, approval_manager=appr_mgr)

        res = await tool.execute({"path": "code.py", "new_content": "old_code = False\n"})
        assert res["applied"] is False
        assert "declined" in res["message"].lower()

        # Content on disk must NOT have changed
        assert f.read_text(encoding="utf-8") == "old_code = True\n"
    asyncio.run(_test())


def test_edit_file_tool_approval_accepted(tmp_path):
    async def _test():
        f = tmp_path / "code.py"
        f.write_text("val = 1\n", encoding="utf-8")

        appr_mgr = ApprovalManager(interactive_prompt_func=lambda a, d: True)
        tool = EditFileTool(workspace_root=tmp_path, approval_manager=appr_mgr)

        res = await tool.execute({"path": "code.py", "new_content": "val = 2\n"})
        assert res["applied"] is True
        assert f.read_text(encoding="utf-8") == "val = 2\n"
    asyncio.run(_test())


def test_edit_file_concurrent_conflict(tmp_path):
    async def _test():
        f = tmp_path / "code.py"
        f.write_text("disk_content\n", encoding="utf-8")

        appr_mgr = ApprovalManager(interactive_prompt_func=lambda a, d: True)
        tool = EditFileTool(workspace_root=tmp_path, approval_manager=appr_mgr)

        res = await tool.execute({
            "path": "code.py",
            "new_content": "new_content\n",
            "expected_original": "stale_memory_content\n",
        })
        assert "concurrent_conflict" in res
        assert res["concurrent_conflict"] is True
    asyncio.run(_test())


def test_run_command_tool(tmp_path):
    async def _test():
        appr_mgr = ApprovalManager(interactive_prompt_func=lambda a, d: True)
        tool = RunCommandTool(workspace_root=tmp_path, approval_manager=appr_mgr)

        res = await tool.execute({"command": "echo hello_agentops"})
        assert res["exit_code"] == 0
        assert "hello_agentops" in res["stdout"]
    asyncio.run(_test())


def test_run_command_tool_declined(tmp_path):
    async def _test():
        appr_mgr = ApprovalManager(interactive_prompt_func=lambda a, d: False)
        tool = RunCommandTool(workspace_root=tmp_path, approval_manager=appr_mgr)

        res = await tool.execute({"command": "echo test"})
        assert res["approved"] is False
        assert "cancelled" in res["error"].lower()
    asyncio.run(_test())

