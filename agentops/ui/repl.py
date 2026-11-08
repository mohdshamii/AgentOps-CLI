"""
Interactive REPL loop for AgentOpsCLI using prompt_toolkit and Rich.
"""

import asyncio
import os
import sys
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory

from agentops.core.agent import AgentOpsEngine
from agentops.config.loader import get_agentops_home
from agentops.ui.terminal import TerminalUI
from agentops.ui.shortcuts import handle_slash_command


async def run_repl(engine: AgentOpsEngine, ui: Optional[TerminalUI] = None) -> None:
    """Runs the main interactive agent loop."""
    ui = ui or TerminalUI(theme_name=engine.config.ui.theme)

    # Attach interactive approval prompt
    engine.approval_manager.interactive_prompt_func = ui.prompt_user_approval

    # Print startup banner
    provider_name = engine.config.preferred_provider
    model_name = engine.config.providers.get(provider_name, {}).big_model if provider_name in engine.config.providers else "auto"
    ui.print_banner(version="1.0.0", provider=provider_name, model=model_name)

    history_file = str(get_agentops_home() / "history.txt")
    session = PromptSession(history=FileHistory(history_file))

    while True:
        try:
            # Prompt user
            prompt_text = await session.prompt_async("\n❯ ")
            clean_prompt = prompt_text.strip()
            if not clean_prompt:
                continue

            # Check slash command
            if clean_prompt.startswith("/"):
                handled = handle_slash_command(clean_prompt, engine, ui)
                if handled:
                    continue

            if clean_prompt.lower() in ("exit", "quit"):
                ui.console.print("[dim]Exiting AgentOpsCLI. Goodbye![/dim]")
                break

            # Execute turn
            ui.console.print("")
            result = await engine.execute_prompt(
                prompt=clean_prompt,
                stream=engine.config.ui.stream_output,
                stream_callback=ui.print_stream_delta,
            )

            # Trailing newline after stream completes
            if engine.config.ui.stream_output:
                ui.console.print("")

            # Print status bar
            ui.print_status_bar(
                provider=result["provider"],
                model=result["model"],
                tokens=result["input_tokens"] + result["output_tokens"],
                cost=result["cost_usd"],
            )

        except (KeyboardInterrupt, asyncio.CancelledError):
            ui.console.print("\n[yellow]Operation cancelled by user (Ctrl+C).[/yellow]")
            continue
        except EOFError:
            ui.console.print("\n[dim]Exiting AgentOpsCLI. Goodbye![/dim]")
            break
        except Exception as e:
            ui.print_error(str(e))
