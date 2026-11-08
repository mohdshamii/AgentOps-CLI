"""
Unit tests for context indexer, ignore filtering, token budgeting, and context assembly.
"""

from pathlib import Path
import pytest
from agentops.context.ignore import IgnoreFilter
from agentops.context.indexer import RepositoryIndexer, is_binary_file
from agentops.context.token_budget import TokenBudget, truncate_to_token_budget
from agentops.context.builder import ContextBuilder


def test_ignore_filter(tmp_path):
    (tmp_path / ".gitignore").write_text("*.log\ntemp/\n", encoding="utf-8")
    filter = IgnoreFilter(tmp_path)

    assert filter.is_ignored(".git/config") is True
    assert filter.is_ignored("node_modules/pkg/index.js") is True
    assert filter.is_ignored("__pycache__/app.cpython-310.pyc") is True
    assert filter.is_ignored("debug.log") is True
    assert filter.is_ignored("temp/file.txt") is True
    assert filter.is_ignored("src/main.py") is False


def test_is_binary_file(tmp_path):
    text_file = tmp_path / "hello.txt"
    text_file.write_text("Hello, world!", encoding="utf-8")
    assert is_binary_file(text_file) is False

    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04")
    assert is_binary_file(bin_file) is True


def test_repository_indexer(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('test')", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")

    indexer = RepositoryIndexer(tmp_path)
    indexed = indexer.scan_files()
    rel_paths = [f.relative_path for f in indexed]

    assert "src/app.py" in rel_paths
    assert ".git/HEAD" not in rel_paths


def test_token_budget_truncation():
    budget = TokenBudget(total_budget=1000, per_file_max=500)
    assert budget.remaining == 1000

    allocated = budget.allocate(300)
    assert allocated == 300
    assert budget.used_tokens == 300
    assert budget.remaining == 700

    long_text = "a" * 4000
    truncated, was_trunc = truncate_to_token_budget(long_text, token_limit=100)
    assert was_trunc is True
    assert len(truncated) < len(long_text)
    assert "TRUNCATED" in truncated


def test_context_builder(tmp_path):
    (tmp_path / "router.py").write_text("class SmartRouter:\n    pass\n", encoding="utf-8")
    (tmp_path / "database.py").write_text("class Database:\n    pass\n", encoding="utf-8")

    indexer = RepositoryIndexer(tmp_path)
    builder = ContextBuilder(indexer, max_context_tokens=1000, per_file_max_tokens=500)

    pkg = builder.build_context("How does SmartRouter work?")
    assert "router.py" in pkg.included_files
    assert "--- FILE: router.py ---" in pkg.prompt_context
    assert "class SmartRouter:" in pkg.prompt_context

