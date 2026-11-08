"""
Doctor command for diagnostic and environment health checks.
Replaces scripts/system-check.ts.
"""

import asyncio
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from agentops.config.loader import load_config
from agentops.ui.terminal import TerminalUI


async def check_ollama(base_url: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"ok": True, "detail": f"Running ({len(models)} models available: {', '.join(models[:3])})"}
            return {"ok": False, "detail": f"Status code {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "detail": f"Connection failed: {e}"}


def run_doctor_checks(workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    ws = workspace_root or Path.cwd()
    config = load_config(ws)
    results: List[Dict[str, Any]] = []

    # 1. Python version
    py_ver = platform.python_version()
    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 10:
        results.append({"name": "Python Version", "ok": True, "detail": f"{py_ver} (>= 3.10 required)"})
    else:
        results.append({"name": "Python Version", "ok": False, "detail": f"{py_ver} (< 3.10 is not supported)"})

    # 2. Operating System
    results.append({"name": "Operating System", "ok": True, "detail": f"{platform.system()} {platform.release()}"})

    # 3. Workspace
    results.append({"name": "Workspace Directory", "ok": True, "detail": str(ws)})

    # 4. Git installation
    git_bin = shutil.which("git")
    if git_bin:
        results.append({"name": "Git Command", "ok": True, "detail": git_bin})
    else:
        results.append({"name": "Git Command", "ok": False, "detail": "git is not installed or not in PATH"})

    # 5. Ollama reachability
    ollama_url = config.providers.get("ollama", {}).base_url or "http://localhost:11434"
    ollama_res = asyncio.run(check_ollama(ollama_url))
    results.append({"name": "Local Ollama Endpoint", "ok": ollama_res["ok"], "detail": ollama_res["detail"]})

    # 6. Cloud Provider Keys
    openai_key = config.providers.get("openai", {}).api_key or os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "SUA_CHAVE":
        results.append({"name": "OpenAI Credentials", "ok": True, "detail": "Configured"})
    else:
        results.append({"name": "OpenAI Credentials", "ok": False, "detail": "Not configured (optional for cloud mode)"})

    anthropic_key = config.providers.get("anthropic", {}).api_key or os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        results.append({"name": "Anthropic Credentials", "ok": True, "detail": "Configured"})
    else:
        results.append({"name": "Anthropic Credentials", "ok": False, "detail": "Not configured (optional for Claude models)"})

    gemini_key = config.providers.get("gemini", {}).api_key or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        results.append({"name": "Google Gemini Credentials", "ok": True, "detail": "Configured"})
    else:
        results.append({"name": "Google Gemini Credentials", "ok": False, "detail": "Not configured (optional for Gemini)"})

    all_ok = all(r["ok"] for r in results if r["name"] in ("Python Version", "Operating System", "Workspace Directory"))
    return {
        "status": "healthy" if all_ok else "warning",
        "preferred_provider": config.preferred_provider,
        "checks": results,
    }


def execute_doctor(json_output: bool = False, out_file: Optional[str] = None) -> int:
    report = run_doctor_checks()

    if json_output:
        formatted = json.dumps(report, indent=2)
        if out_file:
            Path(out_file).write_text(formatted, encoding="utf-8")
        print(formatted)
        return 0

    ui = TerminalUI()
    ui.console.print("\n[bold cyan]AgentOpsCLI Runtime Diagnostic Checks[/bold cyan]")
    ui.console.print("=" * 60)

    for c in report["checks"]:
        symbol = "[bold green]✓ PASS[/bold green]" if c["ok"] else "[bold yellow]! WARN[/bold yellow]"
        ui.console.print(f" {symbol} [bold]{c['name']:<25}[/bold] {c['detail']}")

    ui.console.print("=" * 60)
    ui.console.print(f"Overall status: [bold]{report['status'].upper()}[/bold] (Active: {report['preferred_provider']})\n")

    if out_file:
        Path(out_file).write_text(json.dumps(report, indent=2), encoding="utf-8")
        ui.print_success(f"Diagnostics written to {out_file}")

    return 0

