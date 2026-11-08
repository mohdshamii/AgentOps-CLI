"""
Native Ollama provider for local LLM inference.
Connects directly to the Ollama REST API without third-party heavy SDKs.
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


def normalize_ollama_model(model_name: str) -> str:
    """Strips 'ollama/' prefix if present."""
    if model_name.startswith("ollama/"):
        return model_name[len("ollama/"):]
    return model_name


def anthropic_to_ollama_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts messages with Anthropic/OpenAI text blocks into plain Ollama message dictionaries."""
    ollama_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            ollama_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        text_parts.append("[image]")
                elif isinstance(block, str):
                    text_parts.append(block)
            ollama_messages.append({"role": role, "content": "\n".join(text_parts)})
        else:
            ollama_messages.append({"role": role, "content": str(content)})
    return ollama_messages


class OllamaProvider(BaseProvider):
    name: str = "ollama"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ):
        url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if url.endswith("/"):
            url = url[:-1]
        super().__init__(
            base_url=url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def _convert_messages(self, messages: List[LLMMessage], system: Optional[str] = None) -> List[Dict[str, Any]]:
        raw_msgs = []
        if system:
            raw_msgs.append({"role": "system", "content": system})
        for m in messages:
            raw_msgs.append({"role": m.role, "content": m.get_text_content()})
        return anthropic_to_ollama_messages(raw_msgs)

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
            return []

    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        model = normalize_ollama_model(model)
        ollama_messages = self._convert_messages(messages, system)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        content = msg.get("content", "")

        tool_calls = []
        if "tool_calls" in msg and msg["tool_calls"]:
            for idx, tc in enumerate(msg["tool_calls"]):
                fn = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=f"call_{idx}",
                        name=fn.get("name", "tool"),
                        arguments=fn.get("arguments", {}),
                    )
                )

        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        total_tokens = prompt_eval_count + eval_count

        return LLMResponse(
            id=f"ollama_{data.get('created_at', 'resp')}",
            content=content,
            model=model,
            role="assistant",
            tool_calls=tool_calls,
            usage=UsageMetadata(
                input_tokens=prompt_eval_count,
                output_tokens=eval_count,
                total_tokens=total_tokens,
                estimated_cost=0.0,
                is_estimated=False,
            ),
            finish_reason=data.get("done_reason", "stop"),
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
        model = normalize_ollama_model(model)
        ollama_messages = self._convert_messages(messages, system)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk_json = json.loads(line)
                        msg = chunk_json.get("message", {})
                        delta = msg.get("content", "")
                        done = chunk_json.get("done", False)

                        usage = None
                        if done:
                            prompt_eval = chunk_json.get("prompt_eval_count", 0)
                            eval_c = chunk_json.get("eval_count", 0)
                            usage = UsageMetadata(
                                input_tokens=prompt_eval,
                                output_tokens=eval_c,
                                total_tokens=prompt_eval + eval_c,
                                estimated_cost=0.0,
                                is_estimated=False,
                            )

                        yield StreamChunk(
                            delta_text=delta,
                            finish_reason=chunk_json.get("done_reason") if done else None,
                            usage=usage,
                        )
                    except json.JSONDecodeError:
                        continue

