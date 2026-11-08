"""
Terminal rendering and formatted output using Rich.
"""

from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from agentops.ui.themes import get_theme, Theme


class TerminalUI:
    def __init__(self, theme_name: str = "dark", force_terminal: bool = True):
        self.console = Console(force_terminal=force_terminal)
        self.theme: Theme = get_theme(theme_name)

    def set_theme(self, theme_name: str) -> None:
        self.theme = get_theme(theme_name)

    def print_banner(self, version: str = "1.0.0", provider: str = "ollama", model: str = "") -> None:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")

        title = Text("AgentOpsCLI", style=self.theme.primary)
        meta = Text(f"v{version} | Provider: {provider} | Model: {model or 'auto'}", style=self.theme.muted)
        grid.add_row(title, meta)

        banner = Panel(
            grid,
            border_style=self.theme.secondary,
            padding=(0, 1),
            subtitle="[dim]Commercial-grade AI Coding Agent | /help for shortcuts[/dim]",
            subtitle_align="right",
        )
        self.console.print(banner)

    def print_assistant_message(self, text: str) -> None:
        try:
            md = Markdown(text)
            self.console.print(md)
        except Exception:
            self.console.print(text)

    def print_stream_delta(self, delta: str) -> None:
        self.console.print(delta, end="")

    def print_tool_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        self.console.print(f"\n[{self.theme.accent}]⚡ Tool call:[/{self.theme.accent}] [bold]{tool_name}[/bold]")
        for k, v in args.items():
            val_str = str(v)
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            self.console.print(f"   [{self.theme.muted}]{k}:[/{self.theme.muted}] {val_str}")

    def print_diff(self, diff_text: str, filename: str) -> None:
        if not diff_text:
            return
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        panel = Panel(
            syntax,
            title=f"Proposed Diff: {filename}",
            border_style=self.theme.warning,
            padding=(0, 1),
        )
        self.console.print(panel)

    def print_command_prompt(self, command: str, cwd: str) -> None:
        panel = Panel(
            Text(command, style="bold yellow"),
            title=f"Shell Command (cwd: {cwd})",
            border_style=self.theme.warning,
            padding=(0, 1),
        )
        self.console.print(panel)

    def print_status_bar(self, provider: str, model: str, tokens: int, cost: float) -> None:
        status_text = Text()
        status_text.append(" Provider: ", style="bold")
        status_text.append(provider, style="cyan")
        status_text.append(" | Model: ", style="bold")
        status_text.append(model, style="green")
        status_text.append(" | Tokens: ", style="bold")
        status_text.append(str(tokens), style="yellow")
        status_text.append(" | Est. Cost: ", style="bold")
        status_text.append(f"${cost:.4f}", style="magenta")

        self.console.print(Panel(status_text, border_style="dim white", padding=(0, 1)))

    def print_error(self, message: str) -> None:
        self.console.print(f"[{self.theme.danger}]Error:[/{self.theme.danger}] {message}")

    def print_success(self, message: str) -> None:
        self.console.print(f"[{self.theme.success}]✓[/{self.theme.success}] {message}")

    def prompt_user_approval(self, action_type: str, details: Dict[str, Any]) -> bool:
        if action_type == "edit_file":
            self.print_diff(details.get("diff", ""), details.get("path", "file"))
            msg = f"Approve modifying '{details.get('path')}'? [y/N]: "
        elif action_type == "run_command":
            self.print_command_prompt(details.get("command", ""), details.get("cwd", ""))
            msg = f"Approve executing command? [y/N]: "
        else:
            msg = f"Approve action '{action_type}'? [y/N]: "

        try:
            choice = input(msg).strip().lower()
            return choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

