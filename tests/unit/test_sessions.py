"""
Unit tests for session history, atomic persistence, and cost tracking.
"""

from pathlib import Path
import pytest
from agentops.sessions.costs import CostTracker
from agentops.sessions.history import Session, SessionTurn
from agentops.sessions.store import SessionStore


def test_cost_tracker():
    tracker = CostTracker()
    tracker.record_usage("gpt-4o", input_tokens=1000, output_tokens=500, cost_usd=0.0075)
    tracker.record_usage("llama3.1:8b", input_tokens=500, output_tokens=200, cost_usd=0.0)

    summary = tracker.get_summary()
    assert summary.input_tokens == 1500
    assert summary.output_tokens == 700
    assert summary.total_tokens == 2200
    assert summary.estimated_cost_usd == 0.0075
    assert tracker.tokens_by_model["gpt-4o"] == 1500


def test_session_store_save_load_list(tmp_path):
    store = SessionStore(storage_dir=tmp_path)
    session = Session(session_id="test-session-123", name="My Test Session", workspace_dir=str(tmp_path))

    turn = SessionTurn(
        turn_id="turn-1",
        user_prompt="Hello agent",
        assistant_response="Hello developer",
        model="gpt-4o",
        provider="openai",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.0001,
    )
    session.add_turn(turn)

    saved_path = store.save_session(session)
    assert saved_path.is_file()

    loaded = store.load_session("test-session-123")
    assert loaded is not None
    assert loaded.session_id == "test-session-123"
    assert loaded.name == "My Test Session"
    assert len(loaded.turns) == 1
    assert loaded.turns[0].user_prompt == "Hello agent"

    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "test-session-123"


def test_session_store_corrupted_file(tmp_path):
    store = SessionStore(storage_dir=tmp_path)
    bad_file = tmp_path / "corrupted-session.json"
    bad_file.write_text("{invalid json", encoding="utf-8")

    # Corrupted file must not crash load_session or list_sessions
    assert store.load_session("corrupted-session") is None
    assert store.list_sessions() == []


def test_session_export_text(tmp_path):
    store = SessionStore(storage_dir=tmp_path)
    session = Session(session_id="export-test", name="Exportable Session")
    session.add_turn(
        SessionTurn(
            turn_id="t1",
            user_prompt="Why is the sky blue?",
            assistant_response="Rayleigh scattering.",
            model="llama3.1:8b",
            provider="ollama",
        )
    )
    store.save_session(session)

    text = store.export_session_text("export-test")
    assert text is not None
    assert "Why is the sky blue?" in text
    assert "Rayleigh scattering." in text

