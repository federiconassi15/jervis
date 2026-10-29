"""Capability-scoped, read-only Git inspection for Jervis 8.2 Dev Mode.

Only fixed operations are accepted. No shell, hooks, external diffs, network
operations, repository edits, branch resets, or implicit privilege escalation.
Outputs are potentially private and must not be sent to an AI provider without
separate consent and data policy checks.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .capabilities import CapabilityGrant, Principal, authorize

_MAX_OUTPUT = 64 * 1024
_OPERATIONS: dict[str, tuple[str, ...]] = {
    "status": ("status", "--short", "--untracked-files=normal"),
    "diff_check": ("diff", "--no-ext-diff", "--no-textconv", "--check"),
    "diff_stat": ("diff", "--no-ext-diff", "--no-textconv", "--stat"),
    "commits": ("log", "-5", "--format=%h %s"),
}


@dataclass(frozen=True)
class GitInspection:
    operation: str
    success: bool
    output: str
    exit_code: int


def _safe_env() -> dict[str, str]:
    # Avoid inherited Git flags that could enable a pager, credential prompts,
    # tracing, remote helpers, or user-configured external commands.
    environment = {
        name: value for name, value in os.environ.items()
        if not name.startswith("GIT_") and name not in {
            "SSH_ASKPASS", "GIT_ASKPASS", "PAGER", "LESS", "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
        }
    }
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_EXTERNAL_DIFF": "",
    })
    return environment


def inspect_git(root: Path, operation: str, principal: Principal, *,
                grants: tuple[CapabilityGrant, ...] = (),
                timeout_seconds: int = 10) -> GitInspection:
    if operation not in _OPERATIONS:
        raise ValueError("Operation is not allowlisted")
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("Invalid inspection timeout")
    supplied = Path(root).expanduser()
    if supplied.is_symlink() or not supplied.is_dir():
        raise ValueError("Repository must be a real existing directory")
    resolved = supplied.resolve(strict=True)
    decision = authorize(
        principal, "filesystem.read", scope=str(resolved), grants=grants,
    )
    if not decision.permitted:
        raise PermissionError(decision.reason)
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is not installed")

    prefix = [
        git, "-c", "core.fsmonitor=false",
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "diff.external=",
        "-c", "diff.trustExitCode=false",
        "-c", "core.pager=cat",
        "-C", str(resolved),
    ]
    env = _safe_env()
    verify = subprocess.run(
        [*prefix, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_seconds, env=env, check=False,
    )
    if verify.returncode:
        raise ValueError("Path is not an accessible Git repository")
    top = Path(verify.stdout.strip()).resolve(strict=True)
    if top != resolved:
        raise ValueError("Repository path must be its exact approved root")

    result = subprocess.run(
        [*prefix, *_OPERATIONS[operation]],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_seconds, env=env, check=False,
    )
    # Keep this bounded before it is presented or carried to another subsystem.
    output = (result.stdout + result.stderr)[:_MAX_OUTPUT]
    return GitInspection(operation, result.returncode == 0, output, result.returncode)
