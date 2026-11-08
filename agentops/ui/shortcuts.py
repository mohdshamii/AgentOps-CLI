"""
Slash commands and keyboard shortcut handlers for AgentOpsCLI REPL.
"""

import os
from typing import Optional, List, Dict, Any
from agentops.core.agent import AgentOpsEngine
from agentops.ui.terminal import TerminalUI


SLASH_COMMANDS = {
    "/help": "Show available slash commands and shortcuts",
    "/model": "Inspect or set the active model (e.g. /model llama3.1:8b)",
    "/provider": "Inspect or set the active provider (e.g. /provider ollama)",
    "/sessions": "List recent sessions and summaries",
    "/cost": "Show token usage and estimated cost breakdown",
    "/theme": "Switch UI theme between 'dark' and 'light'",
    "/doctor": "Run runtime health and environment diagnostic checks",
    "/clear": "Clear the terminal screen",
    "/exit": "Exit AgentOpsCLI safely",
}


def handle_slash_command(
    command_str: str,
    engine: AgentOpsEngine,
    ui: TerminalUI,
) -> bool:
    """
    Handles a slash command. Returns True if handled, False if regular prompt.
    """
    cmd = command_str.strip()
    if not cmd.startswith("/"):
        return False

    parts = cmd.split(maxsplit=1)
    base_cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if base_cmd in ("/help", "/?"):
        ui.console.print("\n[bold cyan]AgentOpsCLI Slash Commands:[/bold cyan]")
        for sc, desc in SLASH_COMMANDS.items():
            ui.console.print(f"  [bold green]{sc:<12}[/bold green] {desc}")
        ui.console.print("  [dim]Ctrl+C cancels the active operation or exits safely.[/dim]\n")
        return True

    elif base_cmd == "/model":
        if arg:
            engine.config.providers[engine.config.preferred_provider].big_model = arg
            ui.print_success(f"Active model set to '{arg}'")
        else:
            current = engine.config.providers.get(engine.config.preferred_provider)
            model_name = current.big_model if current else "auto"
            ui.console.print(f"Current provider: [bold]{engine.config.preferred_provider}[/bold], Model: [bold green]{model_name}[/bold green]")
        return True

    elif base_cmd == "/provider":
        if arg:
            engine.config.preferred_provider = arg.lower()
            ui.print_success(f"Active provider set to '{arg.lower()}'")
        else:
            ui.console.print(f"Current preferred provider: [bold cyan]{engine.config.preferred_provider}[/bold cyan]")
        return True

    elif base_cmd == "/sessions":
        sessions = engine.session_store.list_sessions()
        ui.console.print(f"\n[bold cyan]Saved Sessions ({len(sessions)}):[/bold cyan]")
        for s in sessions[:10]:
            ui.console.print(
                f"  - [bold]{s['session_id'][:8]}[/bold] ({s['name']}) | Turns: {s['turn_count']} | Tokens: {s['total_tokens']} | Cost: ${s['total_cost_usd']:.4f}"
            )
        ui.console.print("")
        return True

    elif base_cmd == "/cost":
        summary = engine.cost_tracker.get_summary()
        ui.console.print("\n[bold cyan]Session Usage & Cost Breakdown:[/bold cyan]")
        ui.console.print(f"  Input Tokens:  [yellow]{summary.input_tokens}[/yellow]")
        ui.console.print(f"  Output Tokens: [yellow]{summary.output_tokens}[/yellow]")
        ui.console.print(f"  Total Tokens:  [yellow]{summary.total_tokens}[/yellow]")
        ui.console.print(f"  Est. Cost:     [bold green]${summary.estimated_cost_usd:.4f}[/bold green]")
        if engine.cost_tracker.cost_by_model:
            ui.console.print("  Cost by Model:")
            for m, c in engine.cost_tracker.cost_by_model.items():
                toks = engine.cost_tracker.tokens_by_model.get(m, 0)
                ui.console.print(f"    - {m}: ${c:.4f} ({toks} tokens)")
        ui.console.print("")
        return True

    elif base_cmd == "/theme":
        if arg in ("dark", "light"):
            ui.set_theme(arg)
            ui.print_success(f"Theme switched to '{arg}'")
        else:
            new_theme = "light" if ui.theme.name == "dark" else "dark"
            ui.set_theme(new_theme)
            ui.print_success(f"Theme switched to '{new_theme}'")
        return True

    elif base_cmd == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
        ui.print_banner(provider=engine.config.preferred_provider)
        return True

    elif base_cmd in ("/exit", "/quit"):
        ui.console.print("[dim]Exiting AgentOpsCLI. Goodbye![/dim]")
        raise SystemExit(0)

    else:
        ui.print_error(f"Unknown slash command '{base_cmd}'. Type /help for available commands.")
        return True

