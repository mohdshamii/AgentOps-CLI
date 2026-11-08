"""
Task complexity policies and privacy constraints for model routing.
"""

from enum import Enum
from typing import List, Dict, Any


class TaskCategory(str, Enum):
    SIMPLE_EXPLANATION = "simple_explanation"
    CODE_COMPLETION = "code_completion"
    BUG_FIXING = "bug_fixing"
    REFACTORING = "refactoring"
    TEST_GENERATION = "test_generation"
    REPOSITORY_ANALYSIS = "repository_analysis"
    COMPLEX_IMPLEMENTATION = "complex_implementation"


# Keywords used to determine task complexity
COMPLEX_KEYWORDS = [
    "refactor", "rewrite", "architect", "redesign", "multi-file",
    "analyze repository", "full codebase", "pipeline", "dockerfile",
    "migration", "integrate", "benchmark", "performance",
]

SIMPLE_KEYWORDS = [
    "explain", "what is", "meaning of", "summarize", "help", "who is",
    "quick question", "syntax for", "docstring",
]


def classify_task(messages: List[Dict[str, Any]]) -> TaskCategory:
    """Classifies a user task based on message content length and keywords."""
    combined_text = ""
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            combined_text += " " + c
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "text":
                    combined_text += " " + part.get("text", "")

    lower = combined_text.lower()
    total_words = len(lower.split())

    if any(k in lower for k in COMPLEX_KEYWORDS) or total_words > 400:
        return TaskCategory.COMPLEX_IMPLEMENTATION

    if "fix" in lower or "bug" in lower or "error" in lower or "traceback" in lower:
        return TaskCategory.BUG_FIXING

    if "test" in lower or "pytest" in lower or "spec" in lower:
        return TaskCategory.TEST_GENERATION

    if any(k in lower for k in SIMPLE_KEYWORDS) and total_words < 50:
        return TaskCategory.SIMPLE_EXPLANATION

    return TaskCategory.CODE_COMPLETION


def requires_large_model(category: TaskCategory, token_count: int) -> bool:
    """Determines whether a task should use big_model or small_model."""
    if token_count > 3000:
        return True
    if category in (
        TaskCategory.COMPLEX_IMPLEMENTATION,
        TaskCategory.REFACTORING,
        TaskCategory.REPOSITORY_ANALYSIS,
    ):
        return True
    return False


def is_local_provider(provider_name: str, base_url: str = "") -> bool:
    """Checks whether a provider is running locally."""
    if provider_name.lower() == "ollama":
        return True
    lower_url = base_url.lower()
    return "localhost" in lower_url or "127.0.0.1" in lower_url or "::1" in lower_url

