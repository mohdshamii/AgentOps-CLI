"""
Configuration schemas for AgentOpsCLI.
Validated using Pydantic v2 or v1 compatibility.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    name: str = "ollama"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    big_model: str = "llama3.1:8b"
    small_model: str = "llama3.2:3b"
    timeout_seconds: float = 60.0
    max_retries: int = 3


class RouterConfig(BaseModel):
    mode: str = Field(default="smart", description="'smart' or 'fixed'")
    strategy: str = Field(default="balanced", description="'balanced', 'latency', or 'cost'")
    fallback: bool = True
    local_only: bool = False
    max_retries: int = 2
    retry_delay_seconds: float = 1.0


class ContextConfig(BaseModel):
    max_tokens: int = 32000
    per_file_max_tokens: int = 4000
    per_file_max_bytes: int = 500_000
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            "*.pyc",
            "*.lock",
            "*.min.js",
            "*.map",
            ".agentops",
        ]
    )
    include_hidden: bool = False


class SecurityConfig(BaseModel):
    require_approval_for_edits: bool = True
    require_approval_for_commands: bool = True
    workspace_only: bool = True
    masked_env_vars: List[str] = Field(
        default_factory=lambda: [
            "API_KEY",
            "SECRET",
            "TOKEN",
            "PASSWORD",
            "CREDENTIALS",
            "AUTH",
            "PRIVATE_KEY",
        ]
    )


class SessionConfig(BaseModel):
    persistence: bool = True
    storage_dir: Optional[str] = None
    max_history_turns: int = 100


class UIConfig(BaseModel):
    theme: str = "dark"
    syntax_highlight: bool = True
    show_cost: bool = True
    stream_output: bool = True


class AgentOpsConfig(BaseModel):
    preferred_provider: str = "ollama"
    router: RouterConfig = Field(default_factory=RouterConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    custom_settings: Dict[str, Any] = Field(default_factory=dict)

