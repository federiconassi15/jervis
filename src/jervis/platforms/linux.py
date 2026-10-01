from __future__ import annotations

import getpass
import shutil
import subprocess
from pathlib import Path

from .base import PlatformAdapter, PlatformCapabilities
from ..models import Health


def _unit_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class LinuxPlatform(PlatformAdapter):
    unit_name = "jervis.service"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            name="linux",
            desktop_startup="systemd --user",
            server_startup="systemd --user + linger",
            audio_backend="PortAudio / PipeWire / PulseAudio / ALSA host API",
        )

    def unit(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user" / self.unit_name

    def _systemctl(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["systemctl", "--user", *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def _enable_linger(self) -> None:
        loginctl = shutil.which("loginctl")
        if not loginctl:
            raise RuntimeError("loginctl is required for persistent Linux server mode")
        user = getpass.getuser()
        proc = subprocess.run(
            [loginctl, "enable-linger", user],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            sudo = shutil.which("sudo")
            if not sudo:
                raise RuntimeError(
                    "server mode needs systemd linger; run: loginctl enable-linger "
                    + user
                )
            proc = subprocess.run(
                [sudo, loginctl, "enable-linger", user],
                text=True,
                capture_output=True,
                check=False,
            )
        if proc.returncode != 0:
            raise RuntimeError(
                "could not enable systemd linger: "
                + (proc.stderr.strip() or proc.stdout.strip())
            )

    def install_service(
        self,
        executable: Path,
        env: dict[str, str],
        mode: str = "desktop",
    ) -> None:
        if mode not in {"desktop", "server"}:
            raise ValueError("mode must be desktop or server")
        if not shutil.which("systemctl"):
            raise RuntimeError("systemd is required for managed Jervis startup on Linux")

        if mode == "server":
            self._enable_linger()

        unit = self.unit()
        unit.parent.mkdir(parents=True, exist_ok=True)
        env_lines = "".join(
            "Environment=" + _unit_quote(str(key) + "=" + str(value)) + "\n"
            for key, value in sorted(env.items())
        )
        unit.write_text(
            "[Unit]\n"
            "Description=Jervis voice assistant\n"
            "After=network-online.target sound.target\n"
            "Wants=network-online.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            + env_lines
            + "ExecStart="
            + _unit_quote(str(executable))
            + " run\n"
            "Restart=on-failure\n"
            "RestartSec=3\n"
            "TimeoutStopSec=15\n"
            "\n"
            "[Install]\n"
            "WantedBy=default.target\n",
            encoding="utf-8",
        )
        self._systemctl("daemon-reload", check=True)
        self._systemctl("enable", "--now", self.unit_name, check=True)

    def remove_service(self) -> None:
        self._systemctl("disable", "--now", self.unit_name)
        self.unit().unlink(missing_ok=True)
        self._systemctl("daemon-reload")

    def service_installed(self) -> bool:
        return self.unit().is_file()

    def service_health(self) -> Health:
        proc = self._systemctl("is-active", self.unit_name)
        detail = proc.stdout.strip() or proc.stderr.strip() or "inactive"
        return Health(proc.returncode == 0, "service", detail)

    def start_service(self) -> None:
        self._systemctl("start", self.unit_name, check=True)

    def stop_service(self) -> None:
        self._systemctl("stop", self.unit_name)
