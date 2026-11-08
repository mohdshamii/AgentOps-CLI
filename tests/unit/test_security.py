"""
Unit tests for security paths, secrets masking, and approval manager.
"""

from pathlib import Path
import pytest
from agentops.security.paths import resolve_safe_path, is_safe_path, PathSecurityError
from agentops.security.secrets import mask_secrets
from agentops.security.approvals import ApprovalManager, PermissionMode


def test_resolve_safe_path_inside_workspace(tmp_path):
    sub = tmp_path / "src" / "app.py"
    sub.parent.mkdir(parents=True)
    sub.write_text("print('hello')", encoding="utf-8")

    resolved = resolve_safe_path("src/app.py", tmp_path)
    assert resolved == sub.resolve()
    assert is_safe_path("src/app.py", tmp_path) is True


def test_resolve_safe_path_traversal_attack(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(PathSecurityError):
        resolve_safe_path("../secret.txt", ws)

    assert is_safe_path("../secret.txt", ws) is False


def test_mask_secrets():
    text = "Authorization: Bearer sk-ant-api03-1234567890abcdef1234567890"
    masked = mask_secrets(text)
    assert "sk-ant" not in masked
    assert "[REDACTED_CREDENTIAL]" in masked


def test_mask_secrets_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-supersecretkey99999999")
    text = "Sending request with key sk-proj-supersecretkey99999999"
    masked = mask_secrets(text)
    assert "sk-proj-supersecretkey99999999" not in masked
    assert "REDACTED" in masked


def test_approval_manager_default_mode():
    mgr = ApprovalManager(mode=PermissionMode.DEFAULT)
    # Default without callback is False (requires explicit confirmation)
    assert mgr.request_approval("edit_file", {"path": "test.py"}) is False

    # With interactive callback returning True
    mgr.interactive_prompt_func = lambda action, details: True
    assert mgr.request_approval("edit_file", {"path": "test.py"}) is True

    # With interactive callback returning False
    mgr.interactive_prompt_func = lambda action, details: False
    assert mgr.request_approval("edit_file", {"path": "test.py"}) is False


def test_approval_manager_plan_mode():
    mgr = ApprovalManager(mode=PermissionMode.PLAN)
    # Plan mode never approves actions
    mgr.interactive_prompt_func = lambda action, details: True
    assert mgr.request_approval("run_command", {"command": "rm -rf"}) is False


def test_approval_manager_bypass_mode():
    mgr = ApprovalManager(mode=PermissionMode.BYPASS)
    assert mgr.request_approval("run_command", {"command": "echo 1"}) is True

