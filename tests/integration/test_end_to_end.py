"""
Integration test for end-to-end agentic workflow.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from agentops.core.agent import AgentOpsEngine
from agentops.config.defaults import get_default_config
from agentops.security.approvals import PermissionMode
from agentops.providers.base import LLMResponse, ToolCall, UsageMetadata


def test_agent_engine_end_to_end_mock(tmp_path):
    async def _test():
        # Setup workspace file
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)
        py_file = src_dir / "calculator.py"
        py_file.write_text("def add(a, b):\n    return a - b  # Bug!\n", encoding="utf-8")

        cfg = get_default_config()
        cfg.context.ignore_patterns = []

        engine = AgentOpsEngine(
            config=cfg,
            workspace_root=tmp_path,
            permission_mode=PermissionMode.BYPASS,  # Automatically approve for test
        )

        mock_tool_resp = LLMResponse(
            id="resp-1",
            content="I will fix the bug in calculator.py using edit_file.",
            model="llama3.1:8b",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="edit_file",
                    arguments={
                        "path": "src/calculator.py",
                        "new_content": "def add(a, b):\n    return a + b\n",
                    },
                )
            ],
            usage=UsageMetadata(input_tokens=50, output_tokens=30, estimated_cost=0.0),
        )

        mock_final_resp = LLMResponse(
            id="resp-2",
            content="I have fixed the bug in calculator.py.",
            model="llama3.1:8b",
            tool_calls=[],
            usage=UsageMetadata(input_tokens=30, output_tokens=20, estimated_cost=0.0),
        )

        provider = engine.provider_registry.get_provider("ollama")
        provider.chat = AsyncMock(side_effect=[mock_tool_resp, mock_final_resp])

        result = await engine.execute_prompt(
            prompt="Fix the bug in src/calculator.py",
            stream=False,
            provider_override="ollama",
            model_override="llama3.1:8b",
        )

        assert "fixed the bug" in result["response"]
        assert len(result["tool_executions"]) == 1
        assert result["tool_executions"][0]["tool_name"] == "edit_file"
        assert result["tool_executions"][0]["result"]["applied"] is True

        # Verify disk modification
        updated_code = py_file.read_text(encoding="utf-8")
        assert "return a + b" in updated_code

        # Verify session persistence
        saved_session = engine.session_store.load_session(engine.current_session.session_id)
        assert saved_session is not None
        assert len(saved_session.turns) == 1
        assert saved_session.turns[0].user_prompt == "Fix the bug in src/calculator.py"

    asyncio.run(_test())

