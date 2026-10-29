"""Explicit per-user memory curation on top of the existing Jervis State.

Never silently replaces a conflicting memory. No LLM writes, semantic index or
additional personal-data table is introduced by this module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .capabilities import Principal

_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,79}\Z")


@dataclass(frozen=True)
class MemoryChange:
    action: str  # insert, unchanged, conflict
    key: str
    previous: str | None
    proposed: str


def _authorize(principal: Principal) -> None:
    if not principal.user_id or not principal.authenticated or principal.role == "guest":
        raise PermissionError("Authenticated user required")
    if principal.device_id is not None:
        raise PermissionError("Remote memory editing requires a future scoped grant")


def _validate(key: str, value: str) -> None:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("Invalid memory key")
    if (not isinstance(value, str) or not 1 <= len(value) <= 1600
            or "\x00" in value):
        raise ValueError("Invalid memory value")


def preview(state: Any, principal: Principal, key: str,
            value: str) -> MemoryChange:
    _authorize(principal)
    _validate(key, value)
    prior = state.memory(principal.user_id, key)
    if prior is None:
        return MemoryChange("insert", key, None, value)
    previous = prior if isinstance(prior, str) else str(prior)
    if previous == value:
        return MemoryChange("unchanged", key, previous, value)
    return MemoryChange("conflict", key, previous, value)


def apply_explicit(state: Any, principal: Principal, key: str, value: str, *,
                   approve_conflict: bool = False) -> MemoryChange:
    result = preview(state, principal, key, value)
    if result.action == "conflict" and not approve_conflict:
        raise PermissionError("Explicit approval required to replace conflicting memory")
    if result.action != "unchanged":
        state.remember(
            principal.user_id, key, value,
            provenance="8.2:explicit-user", importance=0.85,
        )
    return result


def delete_explicit(state: Any, principal: Principal, key: str) -> None:
    _authorize(principal)
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("Invalid memory key")
    state.forget_memory(principal.user_id, key)
