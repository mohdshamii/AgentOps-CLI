"""
AgentOpsCLI - Main CLI Entrypoint and argument dispatcher.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from agentops import __version__
from agentops.config.loader import load_config
from agentops.core.agent import AgentOpsEngine
from agentops.security.approvals import PermissionMode
from agentops.ui.terminal import TerminalUI
from agentops.ui.repl import run_repl
from agentops.cli.commands.doctor import execute_doctor
from agentops.cli.commands.profile import init_profile, auto_profile, run_profile_recommend
from agentops.cli.commands.mcp import mcp_list, mcp_get, mcp_add_json, mcp_remove
from agentops.cli.commands.auth import auth_status, auth_logout
from agentops.cli.commands.tasks import task_create, task_list, task_update, get_tasks_dir
from agentops.cli.commands.sessions import sessions_list, sessions_export


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentops",
        description="AgentOpsCLI - Commercial-grade AI Coding Agent and CLI Operations Platform.",
    )
    parser.add_argument(
        "-p", "--print",
        dest="print_mode",
        action="store_true",
        help="Print response and exit (useful for pipes and non-interactive scripts).",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json", "stream-json"],
        default="text",
        help="Output format when running in --print mode.",
    )
    parser.add_argument(
        "-m", "--model",
        default=None,
        help="Model to use for the session.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Provider to use (ollama, openai, anthropic, gemini).",
    )
    parser.add_argument(
        "-c", "--continue",
        dest="continue_session",
        action="store_true",
        help="Continue the most recent conversation in the current workspace.",
    )
    parser.add_argument(
        "-r", "--resume",
        default=None,
        help="Resume conversation by session ID.",
    )
    parser.add_argument(
        "--fork-session",
        action="store_true",
        help="When resuming, create a new session ID instead of modifying the existing one.",
    )
    parser.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        help="Bypass all permission checks (recommended only for isolated sandboxes).",
    )
    parser.add_argument(
        "--permission-mode",
        choices=["ask", "plan", "bypass"],
        default="ask",
        help="Permission mode for tools and file edits.",
    )
    parser.add_argument(
        "--bare",
        action="store_true",
        help="Minimal mode: disable background prefetches and auto-discovery.",
    )
    parser.add_argument(
        "--prompt", "-q",
        dest="prompt",
        default=None,
        help="Prompt to execute.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"AgentOpsCLI v{__version__}",
    )

    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # doctor
    doc_parser = subparsers.add_parser("doctor", help="Run system diagnostics and reachability checks.")
    doc_parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    doc_parser.add_argument("--out", default=None, help="Write JSON report to file.")

    # profile
    prof_parser = subparsers.add_parser("profile", help="Manage provider profiles and model recommendations.")
    prof_sub = prof_parser.add_subparsers(dest="profile_action")
    prof_init = prof_sub.add_parser("init", help="Initialize a provider profile.")
    prof_init.add_argument("--provider", default="ollama", help="Provider name.")
    prof_init.add_argument("--model", default=None, help="Model name.")
    prof_init.add_argument("--goal", default="balanced", choices=["coding", "latency", "balanced"], help="Optimization goal.")
    prof_init.add_argument("--api-key", default=None, help="API key if required.")
    prof_init.add_argument("--base-url", default=None, help="Base URL endpoint.")

    prof_rec = prof_sub.add_parser("recommend", help="Recommend best local model for goal.")
    prof_rec.add_argument("--goal", default="coding", choices=["coding", "latency", "balanced"], help="Optimization goal.")

    prof_sub.add_parser("auto", help="Auto-detect best provider/model and persist profile.")

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="Configure Model Context Protocol servers.")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_action")
    mcp_sub.add_parser("list", help="List configured MCP servers.")
    mcp_get_p = mcp_sub.add_parser("get", help="Get details of an MCP server.")
    mcp_get_p.add_argument("name", help="Server name.")

    mcp_add = mcp_sub.add_parser("add-json", help="Add MCP server configuration as JSON.")
    mcp_add.add_argument("name", help="Server name.")
    mcp_add.add_argument("json_str", help="JSON definition string.")
    mcp_add.add_argument("-s", "--scope", default="project", choices=["project", "user"], help="Scope.")

    mcp_rm = mcp_sub.add_parser("remove", help="Remove an MCP server.")
    mcp_rm.add_argument("name", help="Server name.")
    mcp_rm.add_argument("-s", "--scope", default="project", choices=["project", "user"], help="Scope.")

    # auth
    auth_parser = subparsers.add_parser("auth", help="Manage API credentials.")
    auth_sub = auth_parser.add_subparsers(dest="auth_action")
    auth_status_p = auth_sub.add_parser("status", help="Show authentication status.")
    auth_status_p.add_argument("--json", action="store_true", help="Output as JSON.")
    auth_sub.add_parser("logout", help="Clear session credentials from environment.")

    # task
    task_parser = subparsers.add_parser("task", help="Manage task list tasks.")
    task_sub = task_parser.add_subparsers(dest="task_action")
    t_create = task_sub.add_parser("create", help="Create a new task.")
    t_create.add_argument("subject", help="Task subject.")
    t_create.add_argument("-d", "--description", default="", help="Task description.")

    t_list = task_sub.add_parser("list", help="List tasks.")
    t_list.add_argument("--pending", action="store_true", help="Show only pending tasks.")
    t_list.add_argument("--json", action="store_true", help="Output as JSON.")

    t_up = task_sub.add_parser("update", help="Update task status or subject.")
    t_up.add_argument("id", help="Task ID.")
    t_up.add_argument("-s", "--status", default=None, help="Status (pending, done, cancelled).")
    t_up.add_argument("--subject", default=None, help="Updated subject.")

    task_sub.add_parser("dir", help="Show tasks directory path.")

    # sessions
    sess_parser = subparsers.add_parser("sessions", help="Manage conversation sessions.")
    sess_sub = sess_parser.add_subparsers(dest="session_action")
    sess_sub.add_parser("list", help="List saved sessions.")
    sess_exp = sess_sub.add_parser("export", help="Export session text.")
    sess_exp.add_argument("session_id", help="Session ID to export.")
    sess_exp.add_argument("output_file", help="Target output text file.")

    return parser


def preprocess_argv(argv: List[str]) -> Tuple[List[str], Optional[str]]:
    """Separates non-subcommand positional prompt from CLI flags and subcommands."""
    known_subcommands = {"doctor", "profile", "mcp", "auth", "task", "sessions"}
    options_with_value = {
        "-m", "--model", "--provider", "-r", "--resume",
        "--permission-mode", "--output-format", "--prompt", "-q",
    }
    cleaned_argv: List[str] = []
    extracted_prompt: List[str] = []
    skip_next = False

    for i, arg in enumerate(argv):
        if skip_next:
            cleaned_argv.append(arg)
            skip_next = False
            continue
        if arg in options_with_value:
            cleaned_argv.append(arg)
            skip_next = True
            continue
        if arg.startswith("-"):
            cleaned_argv.append(arg)
            continue
        if arg in known_subcommands:
            cleaned_argv.extend(argv[i:])
            break
        else:
            extracted_prompt.append(arg)

    prompt = " ".join(extracted_prompt).strip() if extracted_prompt else None
    return cleaned_argv, prompt


def main(argv: Optional[List[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    cleaned_args, positional_prompt = preprocess_argv(raw_args)

    parser = create_parser()
    args = parser.parse_args(cleaned_args)

    # 1. Handle subcommands
    if args.subcommand == "doctor":
        return execute_doctor(json_output=args.json, out_file=args.out)

    elif args.subcommand == "profile":
        if args.profile_action == "init":
            init_profile(
                provider=args.provider,
                model=args.model,
                goal=args.goal,
                api_key=args.api_key,
                base_url=args.base_url,
            )
            return 0
        elif args.profile_action == "auto":
            auto_profile()
            return 0
        elif args.profile_action == "recommend":
            rec = asyncio.run(run_profile_recommend(args.goal))
            ui = TerminalUI()
            if rec:
                ui.console.print(f"Recommended model for goal '{args.goal}': [bold green]{rec}[/bold green]")
            else:
                ui.console.print(f"[yellow]No local Ollama models found. Start Ollama and run 'ollama pull llama3.1:8b'[/yellow]")
            return 0
        else:
            parser.parse_args(["profile", "--help"])
            return 0

    elif args.subcommand == "mcp":
        if args.mcp_action == "list":
            return mcp_list()
        elif args.mcp_action == "get":
            return mcp_get(args.name)
        elif args.mcp_action == "add-json":
            return mcp_add_json(args.name, args.json_str, scope=args.scope)
        elif args.mcp_action == "remove":
            return mcp_remove(args.name, scope=args.scope)
        else:
            parser.parse_args(["mcp", "--help"])
            return 0

    elif args.subcommand == "auth":
        if args.auth_action == "status":
            return auth_status(json_output=args.json)
        elif args.auth_action == "logout":
            return auth_logout()
        else:
            parser.parse_args(["auth", "--help"])
            return 0

    elif args.subcommand == "task":
        if args.task_action == "create":
            return task_create(args.subject, description=args.description)
        elif args.task_action == "list":
            return task_list(pending_only=args.pending, json_output=args.json)
        elif args.task_action == "update":
            return task_update(args.id, status=args.status, subject=args.subject)
        elif args.task_action == "dir":
            print(str(get_tasks_dir()))
            return 0
        else:
            parser.parse_args(["task", "--help"])
            return 0

    elif args.subcommand == "sessions":
        if args.session_action == "list":
            return sessions_list()
        elif args.session_action == "export":
            return sessions_export(args.session_id, args.output_file)
        else:
            parser.parse_args(["sessions", "--help"])
            return 0

    # 2. Main agent execution (Interactive or Print mode)
    perm_mode = PermissionMode.BYPASS if args.dangerously_skip_permissions else PermissionMode(args.permission_mode)
    config = load_config()

    # Session resolution
    session_id = args.resume
    if args.continue_session and not session_id:
        store = SessionStore()
        latest = store.get_latest_session()
        if latest:
            session_id = latest.session_id

    engine = AgentOpsEngine(
        config=config,
        session_id=session_id,
        permission_mode=perm_mode,
    )

    if args.fork_session and session_id:
        import uuid
        engine.current_session.session_id = str(uuid.uuid4())
        engine.current_session.name = f"{engine.current_session.name} (Fork)"

    resolved_prompt = args.prompt or positional_prompt

    # Print / non-interactive mode
    if args.print_mode or resolved_prompt:
        prompt_text = resolved_prompt
        if not prompt_text:
            if not sys.stdin.isatty():
                prompt_text = sys.stdin.read().strip()
            else:
                print("Error: No prompt provided for print mode.", file=sys.stderr)
                return 1

        async def run_print():
            result = await engine.execute_prompt(
                prompt=prompt_text,
                stream=(args.output_format == "stream-json" or (args.print_mode and args.output_format == "text" and sys.stdout.isatty())),
                model_override=args.model,
                provider_override=args.provider,
                stream_callback=print_stream_chunk if args.output_format == "stream-json" else None,
            )
            return result

        def print_stream_chunk(delta: str):
            chunk = {"type": "content_block_delta", "delta": delta}
            sys.stdout.write(json.dumps(chunk) + "\n")
            sys.stdout.flush()

        res = asyncio.run(run_print())

        if args.output_format == "json":
            print(json.dumps(res, indent=2))
        elif args.output_format == "text":
            print(res["response"])
        return 0

    # Interactive REPL mode
    asyncio.run(run_repl(engine))
    return 0


def cli_entrypoint() -> None:
    """Entry point for pyproject.toml scripts console entry."""
    sys.exit(main())


if __name__ == "__main__":
    cli_entrypoint()
