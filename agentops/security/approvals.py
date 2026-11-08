"""
Explicit user approval management for file modifications and terminal commands.
Guarantees the agent cannot approve its own actions.
"""

from enum import Enum
from typing import Callable, Optional, Dict, Any


class PermissionMode(str, Enum):
    DEFAULT = "ask"
    PLAN = "plan"
    BYPASS = "bypass"


class ApprovalManager:
    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        interactive_prompt_func: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        self.mode = mode
        self.interactive_prompt_func = interactive_prompt_func

    def request_approval(self, action_type: str, details: Dict[str, Any]) -> bool:
        """
        Requests explicit user approval.
        action_type: 'edit_file' | 'run_command'
        details: dict containing command string, diff preview, or target path
        """
        if self.mode == PermissionMode.BYPASS:
            return True

        if self.mode == PermissionMode.PLAN:
            # Plan mode never executes edits or commands
            return False

        if self.interactive_prompt_func:
            return self.interactive_prompt_func(action_type, details)

        # Default fallback if no interactive prompt attached
        return False

