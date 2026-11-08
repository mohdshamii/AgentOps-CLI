"""
Provider registry for managing and instantiating LLM providers.
"""

from typing import Dict, Optional, Type
from agentops.config.schema import AgentOpsConfig
from agentops.providers.base import BaseProvider
from agentops.providers.ollama import OllamaProvider
from agentops.providers.openai_compatible import OpenAICompatibleProvider
from agentops.providers.anthropic import AnthropicProvider
from agentops.providers.gemini import GeminiProvider


class ProviderRegistry:
    def __init__(self, config: AgentOpsConfig):
        self.config = config
        self._instances: Dict[str, BaseProvider] = {}
        self._classes: Dict[str, Type[BaseProvider]] = {
            "ollama": OllamaProvider,
            "openai": OpenAICompatibleProvider,
            "anthropic": AnthropicProvider,
            "gemini": GeminiProvider,
        }

    def register_provider_class(self, name: str, cls: Type[BaseProvider]) -> None:
        self._classes[name.lower()] = cls

    def get_provider(self, name: Optional[str] = None) -> BaseProvider:
        provider_name = (name or self.config.preferred_provider).lower()
        if provider_name in self._instances:
            return self._instances[provider_name]

        cls = self._classes.get(provider_name, OpenAICompatibleProvider)
        p_cfg = self.config.providers.get(provider_name)

        base_url = p_cfg.base_url if p_cfg else None
        api_key = p_cfg.api_key if p_cfg else None
        timeout = p_cfg.timeout_seconds if p_cfg else 60.0

        instance = cls(base_url=base_url, api_key=api_key, timeout_seconds=timeout)
        self._instances[provider_name] = instance
        return instance

    def get_all_providers(self) -> Dict[str, BaseProvider]:
        for name in self._classes:
            self.get_provider(name)
        return dict(self._instances)

