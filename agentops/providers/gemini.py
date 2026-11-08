"""
Google Gemini provider adapter via official OpenAI-compatible endpoint.
"""

import os
from typing import Optional
from agentops.providers.openai_compatible import OpenAICompatibleProvider

GEMINI_MODEL_COSTS = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}


class GeminiProvider(OpenAICompatibleProvider):
    name: str = "gemini"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ):
        url = base_url or os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        super().__init__(
            base_url=url,
            api_key=key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        cost_info = GEMINI_MODEL_COSTS.get(model, {"input": 0.10, "output": 0.40})
        inp_cost = (input_tokens / 1_000_000.0) * cost_info["input"]
        out_cost = (output_tokens / 1_000_000.0) * cost_info["output"]
        return round(inp_cost + out_cost, 6)

