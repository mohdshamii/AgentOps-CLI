"""
Context builder that ranks files by task relevance and builds delimited payloads.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set
from agentops.context.indexer import RepositoryIndexer, IndexedFile
from agentops.context.token_budget import TokenBudget, truncate_to_token_budget


@dataclass
class ContextPackage:
    prompt_context: str
    included_files: List[str] = field(default_factory=list)
    excluded_files: List[str] = field(default_factory=list)
    truncated_files: List[str] = field(default_factory=list)
    total_tokens: int = 0


class ContextBuilder:
    def __init__(
        self,
        indexer: RepositoryIndexer,
        max_context_tokens: int = 24000,
        per_file_max_tokens: int = 4000,
    ):
        self.indexer = indexer
        self.max_context_tokens = max_context_tokens
        self.per_file_max_tokens = per_file_max_tokens

    def score_file(self, file_info: IndexedFile, query: str) -> float:
        """Calculates relevance score between query and a file."""
        q_lower = query.lower()
        rel_lower = file_info.relative_path.lower()
        score = 0.0

        # Exact file name match
        if file_info.path.name.lower() in q_lower:
            score += 100.0

        # Path substring match
        if rel_lower in q_lower:
            score += 80.0

        # Word overlaps in path
        q_words = set(q_lower.replace("/", " ").replace("\\", " ").replace(".", " ").split())
        path_words = set(rel_lower.replace("/", " ").replace("\\", " ").replace(".", " ").split())
        overlap = len(q_words.intersection(path_words))
        score += overlap * 10.0

        # Give small baseline weight for primary code files
        ext = file_info.path.suffix.lower()
        if ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go"):
            score += 2.0
        elif ext in (".md", ".txt", ".json", ".yaml", ".yml"):
            score += 1.0

        # Penalize very large files slightly to prefer concise context
        if file_info.size_bytes > 100_000:
            score -= 1.0

        return score

    def build_context(self, query: str, explicit_files: Optional[List[str]] = None) -> ContextPackage:
        all_files = self.indexer.scan_files()
        budget = TokenBudget(total_budget=self.max_context_tokens, per_file_max=self.per_file_max_tokens)

        # Separate explicit files and auto-ranked files
        explicit_set = set(explicit_files or [])
        prioritized: List[IndexedFile] = []
        regular: List[IndexedFile] = []

        for f in all_files:
            if f.relative_path in explicit_set or str(f.path) in explicit_set:
                prioritized.append(f)
            else:
                regular.append(f)

        # Rank regular files by score
        regular.sort(key=lambda f: self.score_file(f, query), reverse=True)
        ordered_candidates = prioritized + regular

        context_blocks = []
        included = []
        excluded = []
        truncated = []

        for f in ordered_candidates:
            if budget.remaining <= 100:
                excluded.append(f.relative_path)
                continue

            try:
                content = f.path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                excluded.append(f.relative_path)
                continue

            est_tokens = len(content) // 4
            allocated = budget.allocate(est_tokens)

            if allocated <= 0:
                excluded.append(f.relative_path)
                continue

            processed_content, was_truncated = truncate_to_token_budget(content, allocated)
            if was_truncated:
                truncated.append(f.relative_path)

            included.append(f.relative_path)
            block = (
                f"--- FILE: {f.relative_path} ---\n"
                f"{processed_content}\n"
                f"--- END FILE ---"
            )
            context_blocks.append(block)

        combined_text = "\n\n".join(context_blocks)
        return ContextPackage(
            prompt_context=combined_text,
            included_files=included,
            excluded_files=excluded,
            truncated_files=truncated,
            total_tokens=budget.used_tokens,
        )

