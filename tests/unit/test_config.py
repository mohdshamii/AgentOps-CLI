"""
Unit tests for configuration schema, defaults, loader, and environment overrides.
"""

import os
from pathlib import Path
import pytest
from agentops.config.schema import AgentOpsConfig, ProviderConfig, RouterConfig
from agentops.config.defaults import get_default_config, DEFAULT_PROVIDERS
from agentops.config.loader import load_config, save_profile_file, load_profile_file


def test_default_config_structure():
    cfg = get_default_config()
    assert cfg.preferred_provider == "ollama"
    assert "ollama" in cfg.providers
    assert "openai" in cfg.providers
    assert "anthropic" in cfg.providers
    assert "gemini" in cfg.providers
    assert cfg.router.mode == "smart"
    assert cfg.security.require_approval_for_edits is True
    assert cfg.security.require_approval_for_commands is True


def test_env_override_preferred_provider(monkeypatch):
    monkeypatch.setenv("PREFERRED_PROVIDER", "anthropic")
    cfg = load_config()
    assert cfg.preferred_provider == "anthropic"


def test_env_override_router_settings(monkeypatch):
    monkeypatch.setenv("ROUTER_STRATEGY", "cost")
    monkeypatch.setenv("ROUTER_FALLBACK", "false")
    monkeypatch.setenv("LOCAL_ONLY", "1")
    cfg = load_config()
    assert cfg.router.strategy == "cost"
    assert cfg.router.fallback is False
    assert cfg.router.local_only is True


def test_env_override_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-12345")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-anthropic")
    cfg = load_config()
    assert cfg.providers["openai"].api_key == "sk-test-openai-12345"
    assert cfg.providers["anthropic"].api_key == "sk-ant-test-anthropic"


def test_profile_save_and_load(tmp_path):
    profile = {
        "profile": "ollama",
        "model": "llama3.2:3b",
        "goal": "latency",
        "env": {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
    }
    saved_file = save_profile_file(profile, workspace_dir=tmp_path)
    assert saved_file.exists()

    loaded = load_profile_file(workspace_dir=tmp_path)
    assert loaded is not None
    assert loaded["profile"] == "ollama"
    assert loaded["model"] == "llama3.2:3b"

