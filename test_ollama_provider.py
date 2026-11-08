"""
test_ollama_provider.py
Run: pytest test_ollama_provider.py -v
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ollama_provider import (
    normalize_ollama_model,
    anthropic_to_ollama_messages,
    ollama_chat,
    list_ollama_models,
    check_ollama_running,
)

def test_normalize_strips_prefix():
    assert normalize_ollama_model("ollama/llama3:8b") == "llama3:8b"

def test_normalize_no_prefix():
    assert normalize_ollama_model("codellama:34b") == "codellama:34b"

def test_normalize_empty():
    assert normalize_ollama_model("") == ""

def test_converts_string_content():
    messages = [{"role": "user", "content": "Hello!"}]
    result = anthropic_to_ollama_messages(messages)
    assert result == [{"role": "user", "content": "Hello!"}]

def test_converts_text_block_list():
    messages = [{"role": "user", "content": [{"type": "text", "text": "What is Python?"}]}]
    result = anthropic_to_ollama_messages(messages)
    assert result[0]["content"] == "What is Python?"

def test_converts_image_block_to_placeholder():
    messages = [{"role": "user", "content": [{"type": "image", "source": {}}, {"type": "text", "text": "Describe this"}]}]
    result = anthropic_to_ollama_messages(messages)
    assert "[image]" in result[0]["content"]
    assert "Describe this" in result[0]["content"]

def test_converts_multi_turn():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "How are you?"},
    ]
    result = anthropic_to_ollama_messages(messages)
    assert len(result) == 3
    assert result[1]["role"] == "assistant"

def test_ollama_running_true():
    async def _test():
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("ollama_provider.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            result = await check_ollama_running()
        assert result is True
    asyncio.run(_test())

def test_ollama_running_false_on_exception():
    async def _test():
        with patch("ollama_provider.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection refused"))
            result = await check_ollama_running()
        assert result is False
    asyncio.run(_test())

def test_list_models_returns_names():
    async def _test():
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:8b", "size": 4000000000},
                {"name": "codellama:34b", "size": 19000000000},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        with patch("ollama_provider.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            models = await list_ollama_models()
        assert "llama3:8b" in models
        assert "codellama:34b" in models
    asyncio.run(_test())

def test_ollama_chat_returns_anthropic_format():
    async def _test():
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Hello back!"},
            "created_at": "2024-01-01T00:00:00Z",
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_response.raise_for_status = MagicMock()
        with patch("ollama_provider.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await ollama_chat(
                model="llama3:8b",
                messages=[{"role": "user", "content": "Hello"}],
            )
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"][0]["text"] == "Hello back!"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5
    asyncio.run(_test())

def test_ollama_chat_prepends_system():
    async def _test():
        captured_payload = {}
        async def mock_post(url, json=None):
            nonlocal captured_payload
            captured_payload = json
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "ok"},
                "created_at": "now",
                "prompt_eval_count": 5,
                "eval_count": 2,
            }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("ollama_provider.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = mock_post
            await ollama_chat(
                model="llama3:8b",
                messages=[{"role": "user", "content": "test"}],
                system="You are a helpful assistant.",
            )
        assert captured_payload["messages"][0]["role"] == "system"
        assert captured_payload["messages"][0]["content"] == "You are a helpful assistant."
    asyncio.run(_test())
