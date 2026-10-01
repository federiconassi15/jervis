from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .base import PlatformAdapter, PlatformCapabilities
from ..models import Health


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _cmd_argument(wrapper: Path) -> str:
    return '/d /c ""' + str(wrapper) + '""'


class WindowsPlatform(PlatformAdapter):
    task_name = "Jervis Voice Assistant"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            name="windows",
            desktop_startup="Task Scheduler at user logon",
            server_startup="persistent Task Scheduler task in the interactive audio session",
            audio_backend="WASAPI / DirectSound / MME through PortAudio",
        )

    def _powershell(
        self,
        script: str,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            text=True,
            capture_output=True,
            check=check,
        )

    def wrapper(self, executable: Path) -> Path:
        return executable.parent / "jervis-service.cmd"

    def install_service(
        self,
        executable: Path,
        env: dict[str, str],
        mode: str = "desktop",
    ) -> None:
        if mode not in {"desktop", "server"}:
            raise ValueError("mode must be desktop or server")

        wrapper = self.wrapper(executable)
        lines = ["@echo off"]
        for key, value in sorted(env.items()):
            safe_value = str(value).replace("%", "%%").replace('"', '""')
            lines.append('set "' + str(key) + "=" + safe_value + '"')
        lines.append('call "' + str(executable) + '" run')
        wrapper.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

        action = (
            "$a=New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "
            + _ps_quote(_cmd_argument(wrapper))
            + ";"
        )
        trigger = "$t=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;"
        principal = (
            "$p=New-ScheduledTaskPrincipal -UserId $env:USERNAME "
            "-LogonType Interactive -RunLevel Limited;"
        )
        settings = (
            "$s=New-ScheduledTaskSettingsSet "
            "-RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) "
            "-ExecutionTimeLimit ([TimeSpan]::Zero) "
            "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
        )
        register = (
            "Register-ScheduledTask -TaskName "
            + _ps_quote(self.task_name)
            + " -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null;"
        )
        self._powershell(
            action + trigger + principal + settings + register,
            check=True,
        )
        self.start_service()

    def remove_service(self) -> None:
        script = (
            "Unregister-ScheduledTask -TaskName "
            + _ps_quote(self.task_name)
            + " -Confirm:$false -ErrorAction SilentlyContinue"
        )
        self._powershell(script)
        install_root = os.environ.get("JERVIS_INSTALL_ROOT")
        if install_root:
            (Path(install_root) / "bin" / "jervis-service.cmd").unlink(missing_ok=True)

    def service_health(self) -> Health:
        script = (
            "$task=Get-ScheduledTask -TaskName "
            + _ps_quote(self.task_name)
            + " -ErrorAction SilentlyContinue;"
            "if($null -eq $task){exit 3};"
            "$info=Get-ScheduledTaskInfo -TaskName "
            + _ps_quote(self.task_name)
            + ";"
            "Write-Output ($task.State.ToString() + ' / LastResult=' + $info.LastTaskResult);"
            "exit 0"
        )
        proc = self._powershell(script)
        detail = proc.stdout.strip() or proc.stderr.strip() or "not installed"
        return Health(proc.returncode == 0, "service", detail)

    def start_service(self) -> None:
        script = (
            "Start-ScheduledTask -TaskName "
            + _ps_quote(self.task_name)
            + " -ErrorAction Stop"
        )
        self._powershell(script, check=True)

    def stop_service(self) -> None:
        script = (
            "Stop-ScheduledTask -TaskName "
            + _ps_quote(self.task_name)
            + " -ErrorAction SilentlyContinue"
        )
        self._powershell(script)
