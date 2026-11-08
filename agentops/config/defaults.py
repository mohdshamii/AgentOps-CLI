"""
Default provider and application settings for AgentOpsCLI.
"""

from agentops.config.schema import ProviderConfig, AgentOpsConfig


DEFAULT_PROVIDERS = {
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434",
        big_model="llama3.1:8b",
        small_model="llama3.2:3b",
        timeout_seconds=120.0,
    ),
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        big_model="gpt-4o",
        small_model="gpt-4o-mini",
        timeout_seconds=60.0,
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        base_url="https://api.anthropic.com/v1",
        big_model="claude-3-5-sonnet-20241022",
        small_model="claude-3-5-haiku-20241022",
        timeout_seconds=60.0,
    ),
    "gemini": ProviderConfig(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        big_model="gemini-2.0-flash",
        small_model="gemini-2.0-flash-lite",
        timeout_seconds=60.0,
    ),
}


def get_default_config() -> AgentOpsConfig:
    cfg = AgentOpsConfig()
    cfg.providers = {k: v.model_copy() if hasattr(v, 'model_copy') else v.copy() for k, v in DEFAULT_PROVIDERS.items()}
    return cfg

