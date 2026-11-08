"""
Unit tests for providers (Ollama, OpenAI, Anthropic, Gemini, Registry).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from agentops.providers.base import LLMMessage, ToolCall
from agentops.providers.ollama import OllamaProvider, normalize_ollama_model
from agentops.providers.openai_compatible import OpenAICompatibleProvider
from agentops.providers.anthropic import AnthropicProvider
from agentops.providers.gemini import GeminiProvider
from agentops.providers.registry import ProviderRegistry
from agentops.config.defaults import get_default_config


def test_normalize_model_name():
    assert normalize_ollama_model("ollama/llama3.1:8b") == "llama3.1:8b"
    assert normalize_ollama_model("llama3.1:8b") == "llama3.1:8b"


def test_ollama_provider_chat_mock():
    async def _test():
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "I am Ollama."},
            "created_at": "2026-01-01T00:00:00Z",
            "prompt_eval_count": 12,
            "eval_count": 8,
            "done_reason": "stop",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            resp = await provider.chat(
                messages=[LLMMessage(role="user", content="Hi")],
                model="llama3.1:8b",
            )
            assert resp.content == "I am Ollama."
            assert resp.model == "llama3.1:8b"
            assert resp.usage.input_tokens == 12
            assert resp.usage.output_tokens == 8
    asyncio.run(_test())


def test_openai_provider_chat_mock():
    async def _test():
        provider = OpenAICompatibleProvider(api_key="sk-test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [{
                "message": {"role": "assistant", "content": "OpenAI Response"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            resp = await provider.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="gpt-4o",
            )
            assert resp.content == "OpenAI Response"
            assert resp.usage.total_tokens == 30
            assert resp.usage.estimated_cost > 0.0
    asyncio.run(_test())


def test_anthropic_provider_chat_mock():
    async def _test():
        provider = AnthropicProvider(api_key="sk-ant-test")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "msg-123",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Claude response"}],
            "usage": {"input_tokens": 15, "output_tokens": 25},
            "stop_reason": "end_turn",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            resp = await provider.chat(
                messages=[LLMMessage(role="user", content="Hello Claude")],
                model="claude-3-5-sonnet-20241022",
            )
            assert resp.content == "Claude response"
            assert resp.usage.input_tokens == 15
            assert resp.usage.output_tokens == 25
            assert resp.usage.estimated_cost > 0.0
    asyncio.run(_test())


def test_gemini_cost_calculation():
    gemini = GeminiProvider(api_key="gemini-key")
    cost = gemini.calculate_cost(input_tokens=100_000, output_tokens=50_000, model="gemini-2.0-flash")
    assert cost > 0.0
    assert cost < 0.10


def test_provider_registry():
    cfg = get_default_config()
    registry = ProviderRegistry(cfg)
    ollama = registry.get_provider("ollama")
    assert isinstance(ollama, OllamaProvider)
    openai = registry.get_provider("openai")
    assert isinstance(openai, OpenAICompatibleProvider)
    anthropic = registry.get_provider("anthropic")
    assert isinstance(anthropic, AnthropicProvider)
    gemini = registry.get_provider("gemini")
    assert isinstance(gemini, GeminiProvider)

