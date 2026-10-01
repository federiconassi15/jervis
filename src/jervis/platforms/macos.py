from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

from .base import PlatformAdapter, PlatformCapabilities
from ..models import Health


class MacOSPlatform(PlatformAdapter):
    label = "ai.jervis.runtime"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            name="macos",
            desktop_startup="launchd LaunchAgent",
            server_startup="persistent LaunchAgent in the logged-in CoreAudio/TCC session",
            audio_backend="CoreAudio through PortAudio",
        )

    def agent_plist(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / (self.label + ".plist")

    def _domain(self) -> str:
        return "gui/" + str(os.getuid())

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

        plist = self.agent_plist()
        plist.parent.mkdir(parents=True, exist_ok=True)
        logs = Path(
            env.get(
                "JERVIS_LOG_HOME",
                str(Path.home() / "Library" / "Logs"),
            )
        )
        logs.mkdir(parents=True, exist_ok=True)

        payload = {
            "Label": self.label,
            "ProgramArguments": [str(executable), "run"],
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 3,
            "ProcessType": "Background" if mode == "server" else "Interactive",
            "EnvironmentVariables": dict(env),
            "StandardOutPath": str(logs / "jervis.log"),
            "StandardErrorPath": str(logs / "jervis-error.log"),
        }

        raw = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)
        plist.write_bytes(raw)

        domain = self._domain()
        self._launchctl("bootout", domain + "/" + self.label)
        subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            check=True,
        )
        subprocess.run(
            ["launchctl", "kickstart", "-k", domain + "/" + self.label],
            check=True,
        )

    def remove_service(self) -> None:
        domain = self._domain()
        subprocess.run(
            ["launchctl", "bootout", domain + "/" + self.label],
            check=False,
        )
        self.agent_plist().unlink(missing_ok=True)

    def service_installed(self) -> bool:
        return self.agent_plist().is_file()

    def service_health(self) -> Health:
        target = self._domain() + "/" + self.label
        proc = self._launchctl("print", target)
        detail = (
            "running"
            if proc.returncode == 0
            else (proc.stderr.strip() or "inactive")
        )
        return Health(proc.returncode == 0, "service", detail)

    def start_service(self) -> None:
        subprocess.run(
            [
                "launchctl",
                "kickstart",
                "-k",
                self._domain() + "/" + self.label,
            ],
            check=True,
        )

    def stop_service(self) -> None:
        subprocess.run(
            [
                "launchctl",
                "kill",
                "SIGTERM",
                self._domain() + "/" + self.label,
            ],
            check=False,
        )
