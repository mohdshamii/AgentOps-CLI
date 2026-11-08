"""
Session turn history and message models.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class ToolExecutionRecord:
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionTurn:
    turn_id: str
    user_prompt: str
    assistant_response: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_executions: List[ToolExecutionRecord] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Session"
    workspace_dir: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: List[SessionTurn] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_turn(self, turn: SessionTurn) -> None:
        self.turns.append(turn)
        self.updated_at = time.time()

    def get_total_tokens(self) -> int:
        return sum(t.input_tokens + t.output_tokens for t in self.turns)

    def get_total_cost(self) -> float:
        return sum(t.cost_usd for t in self.turns)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "workspace_dir": self.workspace_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turns": [asdict(t) for t in self.turns],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        turns = []
        for t_data in data.get("turns", []):
            tool_recs = [
                ToolExecutionRecord(**tr) for tr in t_data.get("tool_executions", [])
            ]
            t_copy = dict(t_data)
            t_copy["tool_executions"] = tool_recs
            turns.append(SessionTurn(**t_copy))

        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            name=data.get("name", "Session"),
            workspace_dir=data.get("workspace_dir", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            turns=turns,
            metadata=data.get("metadata", {}),
        )

