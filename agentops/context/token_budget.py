"""
Token budgeting and allocation logic for context assembly.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class TokenBudget:
    total_budget: int = 32000
    per_file_max: int = 4000
    used_tokens: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total_budget - self.used_tokens)

    def can_fit(self, tokens: int) -> bool:
        return tokens <= self.remaining

    def allocate(self, tokens: int) -> int:
        """Allocates tokens up to per-file maximum and remaining total budget."""
        usable = min(tokens, self.per_file_max, self.remaining)
        self.used_tokens += usable
        return usable


def truncate_to_token_budget(content: str, token_limit: int) -> Tuple[str, bool]:
    """Truncates text content if it exceeds the specified token limit (~4 chars per token)."""
    char_limit = token_limit * 4
    if len(content) <= char_limit:
        return content, False

    truncated = content[:char_limit] + "\n\n... [TRUNCATED - CONTEXT LIMIT REACHED] ..."
    return truncated, True

