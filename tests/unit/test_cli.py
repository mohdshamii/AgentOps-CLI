"""
Unit tests for CLI commands and argument parser.
"""

from pathlib import Path
import pytest
from agentops.cli.main import create_parser, main
from agentops.cli.commands.doctor import run_doctor_checks, execute_doctor
from agentops.cli.commands.mcp import mcp_list, mcp_add_json, mcp_get, mcp_remove
from agentops.cli.commands.auth import auth_status, auth_logout
from agentops.cli.commands.tasks import task_create, task_list, task_update
from agentops.cli.commands.profile import init_profile


def test_parser_options():
    from agentops.cli.main import preprocess_argv, create_parser
    raw = ["-p", "Explain async", "-m", "gpt-4o", "--provider", "openai"]
    cleaned, prompt = preprocess_argv(raw)
    parser = create_parser()
    args = parser.parse_args(cleaned)
    assert args.print_mode is True
    assert prompt == "Explain async"
    assert args.model == "gpt-4o"
    assert args.provider == "openai"


def test_doctor_command():
    report = run_doctor_checks()
    assert "status" in report
    assert "checks" in report
    assert any(c["name"] == "Python Version" for c in report["checks"])
    assert execute_doctor(json_output=True) == 0


def test_profile_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = init_profile(provider="ollama", model="llama3.1:8b", goal="coding")
    assert res["profile"] == "ollama"
    assert res["model"] == "llama3.1:8b"


def test_mcp_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert mcp_list(workspace_root=tmp_path) == 0
    assert mcp_add_json("test-server", '{"command": "npx", "args": ["-y", "test"]}', workspace_root=tmp_path) == 0
    assert mcp_get("test-server", workspace_root=tmp_path) == 0
    assert mcp_remove("test-server", workspace_root=tmp_path) == 0


def test_auth_commands():
    assert auth_status(json_output=True) == 0
    assert auth_logout() == 0


def test_task_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTOPS_HOME", str(tmp_path))
    assert task_create("Test task", description="details") == 0
    assert task_list(json_output=True) == 0


def test_cli_main_doctor(capsys):
    ret = main(["doctor", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Python Version" in captured.out
