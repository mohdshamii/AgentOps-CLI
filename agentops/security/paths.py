"""
Path security enforcement and workspace containment.
Prevents directory traversal attacks and unauthorized file escapes.
"""

import os
from pathlib import Path
from typing import Union


class PathSecurityError(PermissionError):
    """Raised when an operation attempts to escape the authorized workspace."""
    pass


def resolve_safe_path(
    target_path: Union[str, Path],
    workspace_root: Union[str, Path],
    allow_absolute: bool = True,
) -> Path:
    """
    Resolves a path ensuring it stays strictly within the workspace directory.
    Prevents path traversal attacks (e.g., ../../../etc/passwd or C:\\Windows).
    """
    ws = Path(workspace_root).resolve()
    target = Path(target_path)

    if not target.is_absolute():
        resolved = (ws / target).resolve()
    else:
        if not allow_absolute:
            raise PathSecurityError(f"Absolute path '{target}' is not permitted.")
        resolved = target.resolve()

    # Verify containment
    try:
        resolved.relative_to(ws)
    except ValueError:
        raise PathSecurityError(
            f"Path traversal violation: '{target}' resolves to '{resolved}', which is outside workspace '{ws}'."
        )

    return resolved


def is_safe_path(
    target_path: Union[str, Path],
    workspace_root: Union[str, Path],
) -> bool:
    """Returns True if the path is safely inside the workspace, False otherwise."""
    try:
        resolve_safe_path(target_path, workspace_root)
        return True
    except (PathSecurityError, ValueError, Exception):
        return False

