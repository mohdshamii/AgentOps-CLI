"""
OpenAI-compatible provider adapter.
Supports OpenAI, DeepSeek, Groq, vLLM, OpenRouter, and standard /v1 endpoints.
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

# Standard cost table per 1M tokens (USD)
OPENAI_MODEL_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1": {"input": 15.00, "output": 60.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
}


class OpenAICompatibleProvider(BaseProvider):
    name: str = "openai"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ):
        url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if url.endswith("/"):
            url = url[:-1]
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        super().__init__(
            base_url=url,
            api_key=key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        cost_info = OPENAI_MODEL_COSTS.get(model, {"input": 2.50, "output": 10.00})
        inp_cost = (input_tokens / 1_000_000.0) * cost_info["input"]
        out_cost = (output_tokens / 1_000_000.0) * cost_info["output"]
        return round(inp_cost + out_cost, 6)

    async def test_connection(self) -> bool:
        if not self.api_key and not ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []

    def _convert_messages(self, messages: List[LLMMessage], system: Optional[str] = None) -> List[Dict[str, Any]]:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        for msg in messages:
            item: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.get_text_content(),
            }
            if msg.name:
                item["name"] = msg.name
            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id
            formatted.append(item)
        return formatted

    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        openai_messages = self._convert_messages(messages, system)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""

        tool_calls = []
        if "tool_calls" in msg and msg["tool_calls"]:
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                args_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", "call"),
                        name=fn.get("name", "tool"),
                        arguments=args,
                    )
                )

        raw_usage = data.get("usage", {})
        inp_tok = raw_usage.get("prompt_tokens", self.estimate_tokens(str(messages)))
        out_tok = raw_usage.get("completion_tokens", self.estimate_tokens(content))
        cost = self.calculate_cost(inp_tok, out_tok, model)

        return LLMResponse(
            id=data.get("id", "chatcmpl"),
            content=content,
            model=data.get("model", model),
            role="assistant",
            tool_calls=tool_calls,
            usage=UsageMetadata(
                input_tokens=inp_tok,
                output_tokens=out_tok,
                total_tokens=inp_tok + out_tok,
                estimated_cost=cost,
                is_estimated="usage" not in data,
            ),
            finish_reason=choice.get("finish_reason", "stop"),
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
        openai_messages = self._convert_messages(messages, system)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._get_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_str)
                        choice = chunk_json.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        text_delta = delta.get("content") or ""
                        finish_reason = choice.get("finish_reason")

                        yield StreamChunk(
                            delta_text=text_delta,
                            finish_reason=finish_reason,
                        )
                    except json.JSONDecodeError:
                        continue

