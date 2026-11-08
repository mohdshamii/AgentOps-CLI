"""
Unified diff generation and styling.
"""

import difflib
from typing import List


def generate_unified_diff(
    original_text: str,
    new_text: str,
    file_path: str = "file",
) -> str:
    """Generates standard unified diff between original and updated text."""
    orig_lines = original_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )
    return "".join(diff)


def format_colored_diff(diff_text: str) -> str:
    """Formats diff lines with ANSI colors for readable terminal inspection."""
    formatted_lines = []
    for line in diff_text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            formatted_lines.append(f"\033[1;37m{line}\033[0m")
        elif line.startswith("@@"):
            formatted_lines.append(f"\033[36m{line}\033[0m")
        elif line.startswith("+"):
            formatted_lines.append(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            formatted_lines.append(f"\033[31m{line}\033[0m")
        else:
            formatted_lines.append(line)
    return "\n".join(formatted_lines)

