"""
Event types and event emitter for streaming and agent lifecycle observation.
"""

from enum import Enum
from typing import Callable, Dict, List, Any, Union


class EventType(str, Enum):
    STARTUP = "startup"
    PROMPT_START = "prompt_start"
    STREAM_CHUNK = "stream_chunk"
    ASSISTANT_REPLY = "assistant_reply"
    TOOL_CALL_DETECTED = "tool_call_detected"
    TOOL_APPROVAL_REQUEST = "tool_approval_request"
    TOOL_EXECUTED = "tool_executed"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"


class EventEmitter:
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def on(self, event_type: Union[EventType, str], callback: Callable[[Dict[str, Any]], None]) -> None:
        key = str(event_type)
        self._listeners.setdefault(key, []).append(callback)

    def emit(self, event_type: Union[EventType, str], data: Dict[str, Any]) -> None:
        key = str(event_type)
        for cb in self._listeners.get(key, []):
            try:
                cb(data)
            except Exception:
                pass
