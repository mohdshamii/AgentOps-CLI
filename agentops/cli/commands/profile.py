"""
Provider profile configuration, recommendation, and bootstrap command.
Replaces scripts/provider-bootstrap.ts, provider-recommend.ts, provider-launch.ts.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from agentops.config.loader import save_profile_file
from agentops.providers.ollama import OllamaProvider
from agentops.ui.terminal import TerminalUI


RECOMMENDED_MODELS = {
    "coding": [
        "qwen2.5-coder:14b",
        "qwen2.5-coder:7b",
        "deepseek-coder:6.7b",
        "codellama:13b",
        "codellama:7b",
        "llama3.1:8b",
    ],
    "latency": [
        "llama3.2:3b",
        "llama3.2:1b",
        "phi3:mini",
        "mistral:7b",
    ],
    "balanced": [
        "llama3.1:8b",
        "qwen2.5-coder:7b",
        "mistral:7b",
        "llama3.2:3b",
    ],
}


def recommend_model(available_models: List[str], goal: str = "balanced") -> Optional[str]:
    pref_list = RECOMMENDED_MODELS.get(goal.lower(), RECOMMENDED_MODELS["balanced"])
    for pref in pref_list:
        for avail in available_models:
            if pref in avail or avail.startswith(pref):
                return avail

    # Return first available if any
    return available_models[0] if available_models else None


async def run_profile_recommend(goal: str = "coding") -> Optional[str]:
    ollama = OllamaProvider()
    available = await ollama.list_models()
    if not available:
        return None
    return recommend_model(available, goal)


def init_profile(
    provider: str = "ollama",
    model: Optional[str] = None,
    goal: str = "balanced",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    ui = TerminalUI()
    selected_provider = provider.lower()
    selected_model = model

    if selected_provider == "ollama" and not selected_model:
        ollama = OllamaProvider(base_url=base_url)
        available = asyncio.run(ollama.list_models())
        if available:
            selected_model = recommend_model(available, goal)
        else:
            selected_model = "llama3.1:8b"

    elif selected_provider == "openai" and not selected_model:
        selected_model = "gpt-4o"

    elif selected_provider == "anthropic" and not selected_model:
        selected_model = "claude-3-5-sonnet-20241022"

    elif selected_provider == "gemini" and not selected_model:
        selected_model = "gemini-2.0-flash"

    profile_data = {
        "profile": selected_provider,
        "provider": selected_provider,
        "model": selected_model,
        "goal": goal,
        "env": {},
    }
    if api_key:
        if selected_provider == "openai":
            profile_data["env"]["OPENAI_API_KEY"] = api_key
        elif selected_provider == "anthropic":
            profile_data["env"]["ANTHROPIC_API_KEY"] = api_key
        elif selected_provider == "gemini":
            profile_data["env"]["GEMINI_API_KEY"] = api_key

    if base_url:
        if selected_provider == "ollama":
            profile_data["env"]["OLLAMA_BASE_URL"] = base_url
        elif selected_provider == "openai":
            profile_data["env"]["OPENAI_BASE_URL"] = base_url

    saved_path = save_profile_file(profile_data)
    # Also write backwards compatible .openclaude-profile.json
    try:
        import json
        with open(Path.cwd() / ".openclaude-profile.json", "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2)
    except Exception:
        pass

    ui.print_success(f"Profile saved to {saved_path.name}: provider='{selected_provider}', model='{selected_model}'")
    return profile_data


def auto_profile() -> Dict[str, Any]:
    ui = TerminalUI()
    ollama = OllamaProvider()
    is_running = asyncio.run(ollama.test_connection())

    if is_running:
        models = asyncio.run(ollama.list_models())
        rec = recommend_model(models, "balanced")
        ui.console.print(f"[bold green]Discovered local Ollama with model:[/bold green] {rec or 'default'}")
        return init_profile(provider="ollama", model=rec, goal="balanced")
    else:
        ui.console.print("[bold yellow]Ollama not detected locally. Selecting OpenAI mode.[/bold yellow]")
        return init_profile(provider="openai", model="gpt-4o", goal="balanced")

