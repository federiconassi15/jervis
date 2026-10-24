"""Jervis 8.1 declarative plugin commands.

Untrusted plugin packages are NEVER imported, evaluated or executed.
Only static, audited response actions are supported; future capabilities
need separate permissions and an OS-specific process sandbox.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .evolve import discover_plugins

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


@dataclass(frozen=True)
class PluginCommand:
    plugin_id: str
    command: str
    response: str


def discover_commands(root: Path) -> list[PluginCommand]:
    """Read bounded, validated declarative commands from local manifests."""
    allowed = {entry.identifier for entry in discover_plugins(root)}
    results: list[PluginCommand] = []
    seen = set()
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        manifest = directory / "plugin.json"
        if directory.is_symlink() or manifest.is_symlink() or not manifest.is_file():
            continue
        if manifest.stat().st_size > 16384:
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("id") not in allowed:
                continue
            actions = data.get("commands", [])
            if not isinstance(actions, list) or len(actions) > 32:
                continue
            for row in actions:
                if not isinstance(row, dict) or row.get("type") != "response":
                    continue
                name = row.get("name")
                reply = row.get("text")
                if (not isinstance(name, str) or not _IDENTIFIER.fullmatch(name)
                        or not isinstance(reply, str) or not 1 <= len(reply) <= 360
                        or "\x00" in reply):
                    continue
                key = (data["id"], name)
                if key in seen:
                    continue
                results.append(PluginCommand(data["id"], name, reply))
                seen.add(key)
        except (OSError, UnicodeError, ValueError, TypeError):
            continue
    return results


def invoke_static_plugin(root: Path, identifier: str, command: str) -> str:
    """The only supported action is returning static manifest text."""
    if not isinstance(identifier, str) or not isinstance(command, str):
        raise ValueError("Invalid plugin command")
    for candidate in discover_commands(root):
        if candidate.plugin_id == identifier and candidate.command == command:
            return candidate.response
    raise ValueError("Unknown or unapproved declarative plugin action")
