"""
Base provider abstraction and data models for LLM interactions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator, Union


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMMessage:
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None

    def get_text_content(self) -> str:
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            texts = []
            for item in self.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                    elif item.get("type") == "image":
                        texts.append("[image]")
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)
        return str(self.content)


@dataclass
class UsageMetadata:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    is_estimated: bool = False


@dataclass
class LLMResponse:
    id: str
    content: str
    model: str
    role: str = "assistant"
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: UsageMetadata = field(default_factory=UsageMetadata)
    finish_reason: Optional[str] = None


@dataclass
class StreamChunk:
    delta_text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[UsageMetadata] = None


class BaseProvider(ABC):
    name: str = "base"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Executes a non-streaming chat request."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        """Streams assistant response chunks in real time."""
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Lists available models from the provider."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Returns True if the provider is reachable and credentials are valid."""
        pass

    def estimate_tokens(self, text: str) -> int:
        """Conservative token count estimation: ~4 chars per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculates estimated USD cost for model request."""
        return 0.0

