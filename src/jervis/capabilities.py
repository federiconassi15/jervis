"""Jervis 8.2's deny-by-default capability decision model.

This module accepts only an identity already verified by Jervis. A caller cannot
use a forged request to authenticate itself; transport authentication is separate.
No operation executes in this module.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

ROLE_RANK = {"guest": 0, "known": 1, "trusted": 2, "owner": 3}
# Minimum rank; dangerous permissions ALSO need a scoped, unexpired grant.
CAPABILITIES = {
    "system.status.read": 1,
    "logs.read": 2,
    "memory.read": 2,
    "filesystem.read": 2,
    "filesystem.write": 3,
    "process.execute": 3,
    "screen.capture": 3,
    "mission.execute": 3,
    "plugin.install": 3,
    "automation.manage": 3,
    "device.remote_control": 3,
}
PASSIVE_LOCAL = frozenset({"system.status.read"})
# No implicit remote capabilities: every remote request must have a grant.


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    authenticated: bool
    device_id: str | None = None


@dataclass(frozen=True)
class CapabilityGrant:
    user_id: str
    capability: str
    scope: str
    expires_at: float
    device_id: str | None = None


@dataclass(frozen=True)
class Decision:
    permitted: bool
    reason: str


def _within_scope(requested: str, grant_scope: str, capability: str) -> bool:
    if capability.startswith("filesystem."):
        try:
            path = Path(requested).expanduser().resolve(strict=False)
            root = Path(grant_scope).expanduser().resolve(strict=False)
            return path == root or root in path.parents
        except (OSError, ValueError, RuntimeError):
            return False
    return requested == grant_scope


def authorize(principal: Principal, capability: str, *, scope: str = "",
              grants: tuple[CapabilityGrant, ...] = (), now: float | None = None,
              fresh_auth: bool = False) -> Decision:
    """Evaluate policy without side effects. Only the identity layer builds Principal."""
    if capability not in CAPABILITIES:
        return Decision(False, "unsupported capability")
    if not principal.user_id or not principal.authenticated:
        return Decision(False, "authentication required")
    if ROLE_RANK.get(principal.role, -1) < CAPABILITIES[capability]:
        return Decision(False, "insufficient role")
    if capability in PASSIVE_LOCAL and principal.device_id is None:
        return Decision(True, "authenticated local status")
    if capability in {"process.execute", "filesystem.write", "screen.capture",
                      "mission.execute", "plugin.install", "automation.manage",
                      "device.remote_control"} and not fresh_auth:
        return Decision(False, "fresh authorization required")
    if not scope:
        return Decision(False, "explicit resource scope required")
    current = time.time() if now is None else now
    for grant in grants:
        if (grant.user_id == principal.user_id
                and grant.capability == capability
                and grant.expires_at > current
                and grant.device_id == principal.device_id
                and _within_scope(scope, grant.scope, capability)):
            return Decision(True, "scoped grant valid")
    return Decision(False, "no valid scoped grant")
