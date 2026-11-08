"""
Task management commands for AgentOpsCLI.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from agentops.config.loader import get_agentops_home
from agentops.ui.terminal import TerminalUI


def get_tasks_dir() -> Path:
    tasks_dir = get_agentops_home() / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def task_create(subject: str, description: str = "") -> int:
    ui = TerminalUI()
    task_id = str(uuid.uuid4())[:8]
    data = {
        "id": task_id,
        "subject": subject,
        "description": description,
        "status": "pending",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    path = get_tasks_dir() / f"{task_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    ui.print_success(f"Task created: [{task_id}] {subject}")
    return 0


def task_list(pending_only: bool = False, json_output: bool = False) -> int:
    ui = TerminalUI()
    tasks: List[Dict[str, Any]] = []

    for file in sorted(get_tasks_dir().glob("*.json")):
        try:
            task = json.loads(file.read_text(encoding="utf-8"))
            if pending_only and task.get("status") != "pending":
                continue
            tasks.append(task)
        except Exception:
            continue

    if json_output:
        print(json.dumps(tasks, indent=2))
        return 0

    ui.console.print(f"\n[bold cyan]Tasks ({len(tasks)}):[/bold cyan]")
    if not tasks:
        ui.console.print("  [dim]No tasks found. Create one with 'agentops task create <subject>'[/dim]\n")
        return 0

    for t in tasks:
        status_color = "yellow" if t.get("status") == "pending" else "green"
        ui.console.print(
            f"  • [{status_color}][{t.get('status', 'unknown')}][/{status_color}] [bold]{t.get('id')}[/bold]: {t.get('subject')} {t.get('description', '')}"
        )
    ui.console.print("")
    return 0


def task_update(task_id: str, status: Optional[str] = None, subject: Optional[str] = None) -> int:
    ui = TerminalUI()
    path = get_tasks_dir() / f"{task_id}.json"
    if not path.is_file():
        ui.print_error(f"Task '{task_id}' not found.")
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if status:
            data["status"] = status
        if subject:
            data["subject"] = subject
        data["updated_at"] = time.time()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        ui.print_success(f"Task [{task_id}] updated.")
        return 0
    except Exception as e:
        ui.print_error(f"Failed to update task: {e}")
        return 1

