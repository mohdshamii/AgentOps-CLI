"""
Anthropic Messages API provider adapter.
Connects natively to https://api.anthropic.com/v1/messages.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional, AsyncIterator
import httpx

from agentops.providers.base import (
    BaseProvider,
    LLMMessage,
    LLMResponse,
    StreamChunk,
    ToolCall,
    UsageMetadata,
)

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL_COSTS = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
}


class AnthropicProvider(BaseProvider):
    name: str = "anthropic"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ):
        url = base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        if url.endswith("/"):
            url = url[:-1]
        key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        super().__init__(
            base_url=url,
            api_key=key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        cost_info = ANTHROPIC_MODEL_COSTS.get(model, {"input": 3.00, "output": 15.00})
        inp_cost = (input_tokens / 1_000_000.0) * cost_info["input"]
        out_cost = (output_tokens / 1_000_000.0) * cost_info["output"]
        return round(inp_cost + out_cost, 6)

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            # Send a minimal 1-token test call
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.base_url}/messages",
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    headers=self._get_headers(),
                )
                return resp.status_code in (200, 400) # 400 with invalid model is still authenticated
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        anthropic_msgs = []
        for msg in messages:
            role = msg.role
            if role == "system":
                continue  # System prompt is passed top-level in Anthropic API
            if role not in ("user", "assistant"):
                role = "user"
            anthropic_msgs.append({
                "role": role,
                "content": msg.get_text_content(),
            })
        return anthropic_msgs

    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        anthropic_messages = self._convert_messages(messages)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        if tools:
            # Convert tools to Anthropic tool schema if needed
            anthropic_tools = []
            for t in tools:
                if "function" in t:
                    fn = t["function"]
                    anthropic_tools.append({
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {}),
                    })
                else:
                    anthropic_tools.append(t)
            payload["tools"] = anthropic_tools

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        text_parts = []
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", "call"),
                        name=block.get("name", "tool"),
                        arguments=block.get("input", {}),
                    )
                )

        content = "\n".join(text_parts)
        raw_usage = data.get("usage", {})
        inp_tok = raw_usage.get("input_tokens", self.estimate_tokens(str(messages)))
        out_tok = raw_usage.get("output_tokens", self.estimate_tokens(content))
        cost = self.calculate_cost(inp_tok, out_tok, model)

        return LLMResponse(
            id=data.get("id", "msg"),
            content=content,
            model=data.get("model", model),
            role="assistant",
            tool_calls=tool_calls,
            usage=UsageMetadata(
                input_tokens=inp_tok,
                output_tokens=out_tok,
                total_tokens=inp_tok + out_tok,
                estimated_cost=cost,
                is_estimated=False,
            ),
            finish_reason=data.get("stop_reason", "end_turn"),
        )

    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        anthropic_messages = self._convert_messages(messages)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                json=payload,
                headers=self._get_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    try:
                        event_data = json.loads(data_str)
                        ev_type = event_data.get("type")
                        if ev_type == "content_block_delta":
                            delta = event_data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield StreamChunk(delta_text=delta.get("text", ""))
                        elif ev_type == "message_delta":
                            stop_reason = event_data.get("delta", {}).get("stop_reason")
                            yield StreamChunk(finish_reason=stop_reason)
                    except json.JSONDecodeError:
                        continue

