"""
Authentication management commands for AgentOpsCLI.
"""

import os
from typing import Dict, Any, Optional
from agentops.config.loader import load_config
from agentops.ui.terminal import TerminalUI


def auth_status(json_output: bool = False) -> int:
    config = load_config()
    ui = TerminalUI()

    providers = {
        "ollama": {
            "configured": True,
            "details": "Local service (no API key required)",
        },
        "openai": {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "details": "OPENAI_API_KEY set" if os.getenv("OPENAI_API_KEY") else "Not configured",
        },
        "anthropic": {
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "details": "ANTHROPIC_API_KEY set" if os.getenv("ANTHROPIC_API_KEY") else "Not configured",
        },
        "gemini": {
            "configured": bool(os.getenv("GEMINI_API_KEY")),
            "details": "GEMINI_API_KEY set" if os.getenv("GEMINI_API_KEY") else "Not configured",
        },
    }

    if json_output:
        import json
        print(json.dumps(providers, indent=2))
        return 0

    ui.console.print("\n[bold cyan]Authentication Status:[/bold cyan]")
    for p_name, p_info in providers.items():
        status = "[bold green]Configured[/bold green]" if p_info["configured"] else "[dim]Missing[/dim]"
        ui.console.print(f"  • [bold]{p_name:<12}[/bold] {status} - {p_info['details']}")
    ui.console.print("")
    return 0


def auth_logout() -> int:
    ui = TerminalUI()
    keys_to_clear = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    for k in keys_to_clear:
        if k in os.environ:
            del os.environ[k]
    ui.print_success("Session credentials cleared from active environment.")
    return 0

