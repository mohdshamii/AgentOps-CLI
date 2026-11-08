"""
Model Context Protocol (MCP) server configuration commands.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from agentops.config.loader import get_agentops_home
from agentops.ui.terminal import TerminalUI


def get_mcp_config_path(workspace_root: Optional[Path] = None, scope: str = "project") -> Path:
    if scope == "user":
        path = get_agentops_home() / "mcp.json"
    else:
        ws = workspace_root or Path.cwd()
        path = ws / ".mcp.json"
    return path


def load_mcp_config(path: Path) -> Dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"mcpServers": {}}
    return {"mcpServers": {}}


def save_mcp_config(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def mcp_list(workspace_root: Optional[Path] = None) -> int:
    ui = TerminalUI()
    path = get_mcp_config_path(workspace_root)
    cfg = load_mcp_config(path)
    servers = cfg.get("mcpServers", {})

    ui.console.print(f"\n[bold cyan]Configured MCP Servers ({len(servers)}):[/bold cyan]")
    if not servers:
        ui.console.print("  [dim]No MCP servers configured. Add one with 'agentops mcp add-json <name> <json>'[/dim]\n")
        return 0

    for name, s_cfg in servers.items():
        cmd = s_cfg.get("command") or s_cfg.get("url", "unknown")
        args = " ".join(s_cfg.get("args", []))
        ui.console.print(f"  • [bold]{name}[/bold]: {cmd} {args}")
    ui.console.print("")
    return 0


def mcp_get(name: str, workspace_root: Optional[Path] = None) -> int:
    ui = TerminalUI()
    path = get_mcp_config_path(workspace_root)
    cfg = load_mcp_config(path)
    server = cfg.get("mcpServers", {}).get(name)

    if not server:
        ui.print_error(f"MCP server '{name}' not found.")
        return 1

    ui.console.print(f"\n[bold cyan]MCP Server: {name}[/bold cyan]")
    ui.console.print(json.dumps(server, indent=2))
    return 0


def mcp_add_json(name: str, json_str: str, scope: str = "project", workspace_root: Optional[Path] = None) -> int:
    ui = TerminalUI()
    try:
        server_def = json.loads(json_str)
    except Exception as e:
        ui.print_error(f"Invalid JSON string: {e}")
        return 1

    path = get_mcp_config_path(workspace_root, scope=scope)
    cfg = load_mcp_config(path)
    cfg.setdefault("mcpServers", {})[name] = server_def
    save_mcp_config(path, cfg)

    ui.print_success(f"Added MCP server '{name}' to {path}")
    return 0


def mcp_remove(name: str, scope: str = "project", workspace_root: Optional[Path] = None) -> int:
    ui = TerminalUI()
    path = get_mcp_config_path(workspace_root, scope=scope)
    cfg = load_mcp_config(path)
    servers = cfg.get("mcpServers", {})

    if name not in servers:
        ui.print_error(f"MCP server '{name}' not found in {path}")
        return 1

    del servers[name]
    save_mcp_config(path, cfg)
    ui.print_success(f"Removed MCP server '{name}' from {path}")
    return 0

