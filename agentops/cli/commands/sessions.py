"""
Session management CLI commands.
"""

from pathlib import Path
from agentops.sessions.store import SessionStore
from agentops.ui.terminal import TerminalUI


def sessions_list() -> int:
    ui = TerminalUI()
    store = SessionStore()
    sessions = store.list_sessions()

    ui.console.print(f"\n[bold cyan]Saved Sessions ({len(sessions)}):[/bold cyan]")
    if not sessions:
        ui.console.print("  [dim]No sessions found.[/dim]\n")
        return 0

    for s in sessions:
        ui.console.print(
            f"  • [bold]{s['session_id'][:8]}[/bold] ({s['name']}) | Turns: {s['turn_count']} | Tokens: {s['total_tokens']} | Cost: ${s['total_cost_usd']:.4f}"
        )
    ui.console.print("")
    return 0


def sessions_export(session_id: str, output_file: str) -> int:
    ui = TerminalUI()
    store = SessionStore()
    text = store.export_session_text(session_id)
    if not text:
        ui.print_error(f"Session '{session_id}' not found.")
        return 1

    try:
        Path(output_file).write_text(text, encoding="utf-8")
        ui.print_success(f"Session exported to {output_file}")
        return 0
    except Exception as e:
        ui.print_error(f"Failed to export session: {e}")
        return 1

