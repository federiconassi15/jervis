from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .openclaw_setup import find_openclaw, run as run_openclaw


def openclaw_agents() -> list[dict[str, Any]]:
    cli = find_openclaw()
    if cli is None:
        return []
    try:
        proc = run_openclaw(cli, "agents", "list", "--json", interactive=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode:
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("agents", "items", "result"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def agent_name(agent: dict[str, Any]) -> str:
    return str(agent.get("name") or agent.get("id") or agent.get("agent") or "").strip()


class AgentHub:
    def __init__(self, state) -> None:
        self.state = state

    def list(self) -> list[dict[str, Any]]:
        return openclaw_agents()

    def selected(self, user_id: str, default: str = "main") -> str:
        value = self.state.get_kv("brain.agent." + user_id, default)
        return str(value or default)

    def select(self, user_id: str, name: str) -> bool:
        clean = name.strip()
        if not clean:
            return False
        available = {agent_name(item) for item in self.list()}
        if clean not in available:
            return False
        self.state.set_kv("brain.agent." + user_id, clean)
        self.state.event("agent_selected", "user=" + user_id + " agent=" + clean)
        return True
