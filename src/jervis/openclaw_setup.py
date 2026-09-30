from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

Progress = Callable[[str], None]


def find_openclaw() -> Path | None:
    found = shutil.which("openclaw")
    if found:
        return Path(found)

    home = Path.home()
    candidates: list[Path] = []
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        candidates += [appdata / "npm" / "openclaw.cmd", appdata / "npm" / "openclaw.exe"]
    else:
        candidates += [
            home / ".npm-global" / "bin" / "openclaw",
            home / ".local" / "bin" / "openclaw",
            home / ".openclaw" / "bin" / "openclaw",
            Path("/opt/homebrew/bin/openclaw"),
            Path("/usr/local/bin/openclaw"),
        ]

    npm = shutil.which("npm")
    if npm:
        try:
            prefix = subprocess.run(
                [npm, "config", "get", "prefix"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            ).stdout.strip()
            if prefix:
                base = Path(prefix)
                candidates += (
                    [base / "openclaw.cmd", base / "openclaw.exe"]
                    if platform.system() == "Windows"
                    else [base / "bin" / "openclaw"]
                )
        except OSError:
            pass

    return next((path for path in candidates if path.exists()), None)


def _command(cli: Path, *args: str) -> list[str]:
    if platform.system() == "Windows" and cli.suffix.lower() in {".cmd", ".bat"}:
        return ["cmd", "/d", "/s", "/c", str(cli), *args]
    return [str(cli), *args]


def run(cli: Path, *args: str, interactive: bool = True) -> subprocess.CompletedProcess[str]:
    kwargs = {"check": False, "text": True}
    if not interactive:
        kwargs["capture_output"] = True
    return subprocess.run(_command(cli, *args), **kwargs)


def install_official(progress: Progress) -> Path:
    progress("Installing OpenClaw using its official installer")
    system = platform.system()

    if system == "Windows":
        payload = urllib.request.urlopen(
            "https://openclaw.ai/install.ps1", timeout=30
        ).read().decode("utf-8")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".ps1", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(payload)
            script = Path(handle.name)
        try:
            proc = subprocess.run(
                [
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(script), "-NoOnboard",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            script.unlink(missing_ok=True)
    else:
        payload = urllib.request.urlopen(
            "https://openclaw.ai/install.sh", timeout=30
        ).read()
        with tempfile.NamedTemporaryFile("wb", suffix=".sh", delete=False) as handle:
            handle.write(payload)
            script = Path(handle.name)
        try:
            proc = subprocess.run(
                ["bash", str(script), "--no-prompt", "--no-onboard", "--verify"],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            script.unlink(missing_ok=True)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown error").strip()[-3000:]
        raise RuntimeError("OpenClaw installer failed: " + detail)

    cli = find_openclaw()
    if not cli:
        raise RuntimeError(
            "OpenClaw installed, but its CLI could not be found in the current session"
        )
    return cli


def doctor(cli: Path) -> tuple[bool, str]:
    proc = run(cli, "doctor", interactive=False)
    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, detail[-3000:]


def configure(cli: Path, mode: str, choose: Callable[[str, list[str], int], int]) -> None:
    choice = choose(
        "OpenClaw model access",
        [
            "ChatGPT / Codex subscription",
            "OpenAI API key",
            "Full OpenClaw setup / another provider",
            "Configure later",
        ],
        0,
    )
    if choice == 3:
        return

    if choice == 0:
        method = "device-code" if mode == "server" else "oauth"
        proc = run(
            cli,
            "models", "auth", "login", "--provider", "openai",
            "--method", method, "--set-default",
            interactive=True,
        )
        if proc.returncode != 0:
            raise RuntimeError("OpenAI/Codex authentication did not complete")
        run(cli, "gateway", "install", interactive=True)
        return

    if choice == 1:
        proc = run(
            cli,
            "models", "auth", "login", "--provider", "openai",
            "--method", "api-key", "--set-default",
            interactive=True,
        )
        if proc.returncode != 0:
            raise RuntimeError("OpenAI API-key authentication did not complete")
        run(cli, "gateway", "install", interactive=True)
        return

    proc = run(cli, "onboard", "--install-daemon", interactive=True)
    if proc.returncode != 0:
        raise RuntimeError("OpenClaw onboarding did not complete")
