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


def agent_capabilities(agent: dict[str, Any]) -> dict[str, Any]:
    """Normalize capability hints without assuming one OpenClaw schema."""
    raw = agent.get("capabilities")
    names: list[str] = []
    cancel_supported = False

    if isinstance(raw, dict):
        for key, value in raw.items():
            if bool(value):
                names.append(str(key))
        cancel_supported = bool(
            raw.get("cancel")
            or raw.get("cancellable")
            or raw.get("cancellation")
        )
    elif isinstance(raw, list):
        names = [str(item) for item in raw if str(item).strip()]
        lowered = {item.lower() for item in names}
        cancel_supported = bool(
            {"cancel", "cancellable", "cancellation"} & lowered
        )
    elif isinstance(raw, str) and raw.strip():
        names = [part.strip() for part in raw.split(",") if part.strip()]
        cancel_supported = any(
            item.lower() in {"cancel", "cancellable", "cancellation"}
            for item in names
        )

    tools = agent.get("tools")
    tool_names: list[str] = []
    if isinstance(tools, list):
        for item in tools:
            if isinstance(item, dict):
                label = item.get("name") or item.get("id")
                if label:
                    tool_names.append(str(label))
            elif str(item).strip():
                tool_names.append(str(item))

    return {
        "name": agent_name(agent),
        "capabilities": sorted(set(names)),
        "tools": sorted(set(tool_names)),
        "cancel_supported": cancel_supported,
        "raw": agent,
    }


class AgentHub:
    def __init__(self, state) -> None:
        self.state = state

    def list(self) -> list[dict[str, Any]]:
        return openclaw_agents()

    def describe(self) -> list[dict[str, Any]]:
        return [
            agent_capabilities(agent)
            for agent in self.list()
            if agent_name(agent)
        ]

    def capability(self, name: str) -> dict[str, Any] | None:
        clean = name.strip()
        return next(
            (
                item
                for item in self.describe()
                if str(item["name"]) == clean
            ),
            None,
        )

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
