from __future__ import annotations

import re
from dataclasses import dataclass

from .openclaw_setup import find_openclaw, run


@dataclass(slots=True)
class OpenClawCompatibility:
    installed: bool
    version: str | None
    wizard_rpc: bool
    detail: str


def check_openclaw_compatibility() -> OpenClawCompatibility:
    cli = find_openclaw()
    if cli is None:
        return OpenClawCompatibility(False, None, False, "OpenClaw is not installed")

    version = None
    try:
        proc = run(cli, "--version", interactive=False, timeout=15)
        text = ((proc.stdout or "") + " " + (proc.stderr or "")).strip()
        match = re.search(r"\b(\d{4}\.\d+\.\d+(?:[-+][\w.-]+)?)\b", text)
        version = match.group(1) if match else (text.splitlines()[0] if text else None)
    except Exception:
        pass

    try:
        proc = run(cli, "gateway", "call", "--help", interactive=False, timeout=15)
        help_text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).lower()
        rpc = proc.returncode == 0 and ("--params" in help_text or "method" in help_text)
    except Exception:
        rpc = False

    detail = (
        "Gateway RPC available; embedded setup supported"
        if rpc
        else "Gateway RPC wizard interface not detected; update OpenClaw before guided setup"
    )
    return OpenClawCompatibility(True, version, rpc, detail)
