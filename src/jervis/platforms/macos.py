from __future__ import annotations

import getpass
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

from .base import PlatformAdapter, PlatformCapabilities
from ..models import Health


class MacOSPlatform(PlatformAdapter):
    label = "ai.jervis.runtime"

    def __init__(self) -> None:
        self._mode = "desktop"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            name="macos",
            desktop_startup="launchd LaunchAgent",
            server_startup="launchd LaunchDaemon",
            audio_backend="CoreAudio through PortAudio",
        )

    def agent_plist(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / (self.label + ".plist")

    def daemon_plist(self) -> Path:
        return Path("/Library/LaunchDaemons") / (self.label + ".plist")

    def _domain(self, mode: str) -> str:
        return "system" if mode == "server" else "gui/" + str(os.getuid())

    def _plist(self, mode: str) -> Path:
        return self.daemon_plist() if mode == "server" else self.agent_plist()

    def _launchctl(
        self,
        *args: str,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["launchctl", *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def install_service(
        self,
        executable: Path,
        env: dict[str, str],
        mode: str = "desktop",
    ) -> None:
        if mode not in {"desktop", "server"}:
            raise ValueError("mode must be desktop or server")
        self._mode = mode

        plist = self._plist(mode)
        logs = Path(env.get("JERVIS_LOG_HOME", str(Path.home() / "Library" / "Logs")))
        logs.mkdir(parents=True, exist_ok=True)

        payload = {
            "Label": self.label,
            "ProgramArguments": [str(executable), "run"],
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 3,
            "EnvironmentVariables": dict(env),
            "StandardOutPath": str(logs / "jervis.log"),
            "StandardErrorPath": str(logs / "jervis-error.log"),
        }
        if mode == "server":
            payload["UserName"] = getpass.getuser()

        with subprocess.Popen(
            ["plutil", "-convert", "xml1", "-o", "-", "--", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            raw = plistlib.dumps(payload)
            stdout, stderr = proc.communicate(raw)
            if proc.returncode != 0:
                raise RuntimeError(
                    "plutil validation failed: " + stderr.decode("utf-8", "replace")
                )
            plist_bytes = stdout

        if mode == "server":
            temp = Path.home() / (".jervis-launchd-" + str(os.getpid()) + ".plist")
            temp.write_bytes(plist_bytes)
            try:
                subprocess.run(
                    ["sudo", "mkdir", "-p", str(plist.parent)],
                    check=True,
                )
                subprocess.run(
                    ["sudo", "cp", str(temp), str(plist)],
                    check=True,
                )
                subprocess.run(
                    ["sudo", "chown", "root:wheel", str(plist)],
                    check=True,
                )
                subprocess.run(
                    ["sudo", "chmod", "644", str(plist)],
                    check=True,
                )
            finally:
                temp.unlink(missing_ok=True)
        else:
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_bytes(plist_bytes)

        domain = self._domain(mode)
        self._launchctl("bootout", domain + "/" + self.label)
        command = ["launchctl", "bootstrap", domain, str(plist)]
        if mode == "server":
            command.insert(0, "sudo")
        subprocess.run(command, check=True)
        kickstart = ["launchctl", "kickstart", "-k", domain + "/" + self.label]
        if mode == "server":
            kickstart.insert(0, "sudo")
        subprocess.run(kickstart, check=True)

    def _detect_mode(self) -> str:
        if self.daemon_plist().exists():
            return "server"
        return "desktop"

    def remove_service(self) -> None:
        mode = self._detect_mode()
        domain = self._domain(mode)
        command = ["launchctl", "bootout", domain + "/" + self.label]
        if mode == "server":
            command.insert(0, "sudo")
        subprocess.run(command, check=False)
        if mode == "server":
            subprocess.run(["sudo", "rm", "-f", str(self.daemon_plist())], check=False)
        else:
            self.agent_plist().unlink(missing_ok=True)

    def service_health(self) -> Health:
        mode = self._detect_mode()
        target = self._domain(mode) + "/" + self.label
        proc = self._launchctl("print", target)
        detail = "running" if proc.returncode == 0 else (proc.stderr.strip() or "inactive")
        return Health(proc.returncode == 0, "service", detail)

    def start_service(self) -> None:
        mode = self._detect_mode()
        command = ["launchctl", "kickstart", "-k", self._domain(mode) + "/" + self.label]
        if mode == "server":
            command.insert(0, "sudo")
        subprocess.run(command, check=True)

    def stop_service(self) -> None:
        mode = self._detect_mode()
        command = ["launchctl", "kill", "SIGTERM", self._domain(mode) + "/" + self.label]
        if mode == "server":
            command.insert(0, "sudo")
        subprocess.run(command, check=False)
