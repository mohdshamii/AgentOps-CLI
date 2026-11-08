"""
Configuration loader with environment variable overrides and profile compatibility.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from dotenv import load_dotenv

from agentops.config.schema import AgentOpsConfig, ProviderConfig
from agentops.config.defaults import get_default_config


def get_agentops_home() -> Path:
    home = Path(os.getenv("AGENTOPS_HOME", Path.home() / ".agentops"))
    home.mkdir(parents=True, exist_ok=True)
    return home


def load_profile_file(workspace_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Loads .agentops-profile.json or legacy .openclaude-profile.json."""
    ws = workspace_dir or Path.cwd()
    candidates = [
        ws / ".agentops-profile.json",
        ws / ".openclaude-profile.json",
        get_agentops_home() / "profile.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def save_profile_file(profile_data: Dict[str, Any], workspace_dir: Optional[Path] = None) -> Path:
    ws = workspace_dir or Path.cwd()
    target = ws / ".agentops-profile.json"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)
    return target


def load_config(workspace_dir: Optional[Path] = None) -> AgentOpsConfig:
    """
    Loads config with order of precedence:
    1. Default values
    2. Global config (~/.agentops/config.yaml or json)
    3. Workspace config (agentops.yaml or agentops.json)
    4. Profile file (.agentops-profile.json or .openclaude-profile.json)
    5. Environment variables (.env and os.environ)
    """
    ws = workspace_dir or Path.cwd()
    env_file = ws / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
    else:
        load_dotenv()

    config = get_default_config()

    # Global config
    global_candidates = [
        get_agentops_home() / "config.yaml",
        get_agentops_home() / "config.json",
    ]
    for gpath in global_candidates:
        if gpath.is_file():
            _merge_from_file(config, gpath)
            break

    # Workspace config
    ws_candidates = [
        ws / "agentops.yaml",
        ws / "agentops.yml",
        ws / "agentops.json",
    ]
    for wspath in ws_candidates:
        if wspath.is_file():
            _merge_from_file(config, wspath)
            break

    # Profile compatibility
    profile = load_profile_file(ws)
    if profile:
        _apply_profile(config, profile)

    # Environment variables
    _apply_env_overrides(config)

    return config


def _merge_from_file(config: AgentOpsConfig, path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8")
        if path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(content) or {}
        else:
            data = json.loads(content)
        
        if "preferred_provider" in data:
            config.preferred_provider = data["preferred_provider"]
        if "router" in data and isinstance(data["router"], dict):
            for k, v in data["router"].items():
                if hasattr(config.router, k):
                    setattr(config.router, k, v)
        if "context" in data and isinstance(data["context"], dict):
            for k, v in data["context"].items():
                if hasattr(config.context, k):
                    setattr(config.context, k, v)
        if "security" in data and isinstance(data["security"], dict):
            for k, v in data["security"].items():
                if hasattr(config.security, k):
                    setattr(config.security, k, v)
        if "ui" in data and isinstance(data["ui"], dict):
            for k, v in data["ui"].items():
                if hasattr(config.ui, k):
                    setattr(config.ui, k, v)
        if "providers" in data and isinstance(data["providers"], dict):
            for p_name, p_data in data["providers"].items():
                if p_name in config.providers:
                    for k, v in p_data.items():
                        if hasattr(config.providers[p_name], k):
                            setattr(config.providers[p_name], k, v)
                else:
                    config.providers[p_name] = ProviderConfig(**p_data)
    except Exception:
        pass


def _apply_profile(config: AgentOpsConfig, profile: Dict[str, Any]) -> None:
    provider_name = profile.get("profile") or profile.get("provider")
    if provider_name:
        config.preferred_provider = str(provider_name).lower()
    
    env_vars = profile.get("env", {})
    if isinstance(env_vars, dict):
        for k, v in env_vars.items():
            if v is not None and k not in os.environ:
                os.environ[k] = str(v)

    model = profile.get("model")
    if model and config.preferred_provider in config.providers:
        config.providers[config.preferred_provider].big_model = model


def _apply_env_overrides(config: AgentOpsConfig) -> None:
    # Preferred provider
    pref = os.getenv("PREFERRED_PROVIDER") or os.getenv("AGENTOPS_PROVIDER")
    if not pref and os.getenv("CLAUDE_CODE_USE_OPENAI") in ("1", "true", "True"):
        pref = "openai"
    if pref:
        config.preferred_provider = pref.lower()

    # Router overrides
    if os.getenv("ROUTER_MODE"):
        config.router.mode = os.getenv("ROUTER_MODE").lower()
    if os.getenv("ROUTER_STRATEGY"):
        config.router.strategy = os.getenv("ROUTER_STRATEGY").lower()
    if os.getenv("ROUTER_FALLBACK"):
        config.router.fallback = os.getenv("ROUTER_FALLBACK").lower() not in ("0", "false", "no")
    if os.getenv("LOCAL_ONLY") or os.getenv("ROUTER_LOCAL_ONLY"):
        config.router.local_only = os.getenv("LOCAL_ONLY", os.getenv("ROUTER_LOCAL_ONLY", "")).lower() in ("1", "true", "yes")

    # Ollama overrides
    ollama_cfg = config.providers.setdefault("ollama", ProviderConfig(name="ollama"))
    if os.getenv("OLLAMA_BASE_URL"):
        ollama_cfg.base_url = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("OLLAMA_MODEL"):
        ollama_cfg.big_model = os.getenv("OLLAMA_MODEL")

    # OpenAI overrides
    openai_cfg = config.providers.setdefault("openai", ProviderConfig(name="openai"))
    if os.getenv("OPENAI_API_KEY"):
        openai_cfg.api_key = os.getenv("OPENAI_API_KEY")
    if os.getenv("OPENAI_BASE_URL"):
        openai_cfg.base_url = os.getenv("OPENAI_BASE_URL")
    if os.getenv("OPENAI_MODEL"):
        openai_cfg.big_model = os.getenv("OPENAI_MODEL")

    # Anthropic overrides
    anthropic_cfg = config.providers.setdefault("anthropic", ProviderConfig(name="anthropic"))
    if os.getenv("ANTHROPIC_API_KEY"):
        anthropic_cfg.api_key = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("ANTHROPIC_BASE_URL"):
        anthropic_cfg.base_url = os.getenv("ANTHROPIC_BASE_URL")
    if os.getenv("ANTHROPIC_MODEL"):
        anthropic_cfg.big_model = os.getenv("ANTHROPIC_MODEL")

    # Gemini overrides
    gemini_cfg = config.providers.setdefault("gemini", ProviderConfig(name="gemini"))
    if os.getenv("GEMINI_API_KEY"):
        gemini_cfg.api_key = os.getenv("GEMINI_API_KEY")
    if os.getenv("GEMINI_BASE_URL"):
        gemini_cfg.base_url = os.getenv("GEMINI_BASE_URL")
    if os.getenv("GEMINI_MODEL"):
        gemini_cfg.big_model = os.getenv("GEMINI_MODEL")

    # Big/Small model general overrides
    if os.getenv("BIG_MODEL"):
        big = os.getenv("BIG_MODEL")
        if config.preferred_provider in config.providers:
            config.providers[config.preferred_provider].big_model = big
    if os.getenv("SMALL_MODEL"):
        small = os.getenv("SMALL_MODEL")
        if config.preferred_provider in config.providers:
            config.providers[config.preferred_provider].small_model = small

