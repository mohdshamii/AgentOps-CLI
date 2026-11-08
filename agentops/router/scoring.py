"""
Provider scoring formulas based on latency, cost, reliability, and error penalty.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderScoreInfo:
    name: str
    healthy: bool = True
    is_configured: bool = True
    avg_latency_ms: float = 9999.0
    cost_per_1k_tokens: float = 0.002
    request_count: int = 0
    error_count: int = 0

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count


def compute_provider_score(
    info: ProviderScoreInfo,
    strategy: str = "balanced",
) -> float:
    """
    Lower score = better provider.
    strategy: 'latency' | 'cost' | 'balanced'
    """
    if not info.healthy or not info.is_configured:
        return float("inf")

    latency_score = info.avg_latency_ms / 1000.0   # normalize to seconds
    cost_score = info.cost_per_1k_tokens * 100.0   # normalize to similar scale
    error_penalty = info.error_rate * 500.0        # heavy penalty for errors

    if strategy == "latency":
        return latency_score + error_penalty
    elif strategy == "cost":
        return cost_score + error_penalty
    else:  # balanced
        return (latency_score * 0.5) + (cost_score * 0.5) + error_penalty

