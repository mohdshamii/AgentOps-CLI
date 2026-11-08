"""
Atomic session persistence and retrieval in ~/.agentops/sessions.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from agentops.config.loader import get_agentops_home
from agentops.sessions.history import Session


class SessionStore:
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (get_agentops_home() / "sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    def save_session(self, session: Session) -> Path:
        """Atomically saves session to disk via temporary file."""
        target_path = self._get_session_path(session.session_id)
        data = session.to_dict()

        tmp_fd, tmp_path_str = tempfile.mkstemp(dir=str(self.storage_dir), prefix="tmp_session_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.replace(tmp_path_str, str(target_path))
        return target_path

    def load_session(self, session_id: str) -> Optional[Session]:
        """Loads a session by ID. Returns None if not found or corrupted."""
        path = self._get_session_path(session_id)
        if not path.is_file():
            # Search by prefix or name
            candidates = list(self.storage_dir.glob(f"{session_id}*.json"))
            if candidates:
                path = candidates[0]
            else:
                return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists all saved sessions with summary statistics."""
        summaries = []
        for file in sorted(self.storage_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                turns = data.get("turns", [])
                tokens = sum(t.get("input_tokens", 0) + t.get("output_tokens", 0) for t in turns)
                cost = sum(t.get("cost_usd", 0.0) for t in turns)

                summaries.append({
                    "session_id": data.get("session_id", file.stem),
                    "name": data.get("name", "Untitled"),
                    "updated_at": data.get("updated_at", 0),
                    "created_at": data.get("created_at", 0),
                    "turn_count": len(turns),
                    "total_tokens": tokens,
                    "total_cost_usd": round(cost, 4),
                    "file_path": str(file),
                })
            except Exception:
                continue
        return summaries

    def get_latest_session(self) -> Optional[Session]:
        """Returns the most recently updated session."""
        sessions = self.list_sessions()
        if not sessions:
            return None
        return self.load_session(sessions[0]["session_id"])

    def delete_session(self, session_id: str) -> bool:
        path = self._get_session_path(session_id)
        if path.is_file():
            try:
                path.unlink()
                return True
            except Exception:
                return False
        return False

    def export_session_text(self, session_id: str) -> Optional[str]:
        session = self.load_session(session_id)
        if not session:
            return None

        lines = [
            f"# Session Export: {session.name} ({session.session_id})",
            f"Created: {session.created_at} | Updated: {session.updated_at}",
            f"Total Turns: {len(session.turns)} | Total Tokens: {session.get_total_tokens()}",
            "=" * 70,
            "",
        ]
        for idx, turn in enumerate(session.turns, start=1):
            lines.append(f"## Turn {idx} [{turn.provider}/{turn.model}]")
            lines.append(f"User: {turn.user_prompt}")
            lines.append(f"Assistant: {turn.assistant_response}")
            if turn.tool_executions:
                lines.append("Tools Executed:")
                for te in turn.tool_executions:
                    lines.append(f"  - {te.tool_name}: {te.arguments} -> {te.result.get('message', 'ok')}")
            lines.append("-" * 40)
            lines.append("")

        return "\n".join(lines)

