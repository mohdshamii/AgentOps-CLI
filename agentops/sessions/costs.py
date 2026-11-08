"""
Token usage and cost tracking for sessions and requests.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class UsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_tokens_count: int = 0
    reported_tokens_count: int = 0


class CostTracker:
    def __init__(self):
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.cost_by_model: Dict[str, float] = {}
        self.tokens_by_model: Dict[str, int] = {}
        self.is_estimated: bool = False

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        is_estimated: bool = False,
    ) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost_usd

        self.cost_by_model[model] = round(self.cost_by_model.get(model, 0.0) + cost_usd, 6)
        total_for_turn = input_tokens + output_tokens
        self.tokens_by_model[model] = self.tokens_by_model.get(model, 0) + total_for_turn

        if is_estimated:
            self.is_estimated = True

    def get_summary(self) -> UsageSummary:
        return UsageSummary(
            input_tokens=self.total_input_tokens,
            output_tokens=self.total_output_tokens,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            estimated_cost_usd=round(self.total_cost_usd, 6),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "is_estimated": self.is_estimated,
            "cost_by_model": self.cost_by_model,
            "tokens_by_model": self.tokens_by_model,
        }

