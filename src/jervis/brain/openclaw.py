from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..openclaw_setup import find_openclaw


@dataclass(slots=True)
class BrainReply:
    ok: bool
    text: str
    error: str = ""


def _run_cli(
    cli: Path,
    args: list[str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    if platform.system() == "Windows" and cli.suffix.lower() in {".cmd", ".bat"}:
        command = subprocess.list2cmdline([str(cli), *args])
        return subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    return subprocess.run(
        [str(cli), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


class OpenClawBrain:
    def __init__(self, agent: str = "main", timeout: int = 60, thinking: str = "low"):
        self.agent = agent
        self.timeout = int(timeout)
        self.thinking = thinking

    @property
    def cli(self) -> Path | None:
        return find_openclaw()

    @property
    def available(self) -> bool:
        return self.cli is not None

    def ask(
        self,
        message: str,
        session_key: str,
        thinking: str | None = None,
    ) -> BrainReply:
        cli = self.cli
        if cli is None:
            return BrainReply(False, "", "OpenClaw is not installed")

        args = [
            "agent",
            "--agent",
            self.agent,
            "--session-key",
            session_key,
            "--message",
            message,
            "--thinking",
            thinking or self.thinking,
            "--timeout",
            str(self.timeout),
            "--json",
        ]
        try:
            proc = _run_cli(cli, args, self.timeout + 10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BrainReply(False, "", str(exc))

        if proc.returncode != 0:
            detail = proc.stderr.strip()
            if not detail:
                try:
                    payload = json.loads(proc.stdout)
                    error = payload.get("error", {}) if isinstance(payload, dict) else {}
                    detail = str(error.get("message") or "")
                except json.JSONDecodeError:
                    detail = ""
            return BrainReply(False, "", detail or "OpenClaw command failed")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return BrainReply(False, "", "OpenClaw returned invalid JSON")

        text = str(data.get("final") or "") if isinstance(data, dict) else ""
        return BrainReply(
            bool(text),
            text,
            "" if text else "OpenClaw returned no final text",
        )

    def doctor(self) -> tuple[bool, str]:
        cli = self.cli
        if cli is None:
            return False, "not installed"
        try:
            proc = _run_cli(cli, ["doctor"], 60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
        return (
            proc.returncode == 0,
            (proc.stdout + proc.stderr).strip()[-2000:],
        )
