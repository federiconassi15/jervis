from __future__ import annotations

import json
import os
import platform
import secrets
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class WizardResult:
    done: bool
    status: str
    step: dict[str, Any] | None = None
    error: str | None = None


class OpenClawWizardBridge:
    """Drive OpenClaw's upstream onboarding wizard through Gateway RPC.

    Jervis renders the returned steps itself, so provider/plugin/API support
    follows the installed OpenClaw version instead of a Jervis-maintained list.
    """

    def __init__(self, cli: Path) -> None:
        self.cli = cli
        self.session_id: str | None = None
        self.gateway_process: subprocess.Popen[str] | None = None
        self.gateway_url = ""
        self.gateway_token = ""
        self._gateway_log = None
        self._gateway_log_path: Path | None = None

    @staticmethod
    def _pick_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _command(self, *args: str) -> tuple[list[str] | str, bool]:
        argv = [str(self.cli), *args]
        if platform.system() == "Windows" and self.cli.suffix.lower() in {".cmd", ".bat"}:
            return subprocess.list2cmdline(argv), True
        return argv, False

    def _run(self, *args: str, timeout: float = 90) -> subprocess.CompletedProcess[str]:
        command, shell = self._command(*args)
        return subprocess.run(
            command,
            shell=shell,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )

    @staticmethod
    def _decode_json(stdout: str) -> dict[str, Any]:
        text = stdout.strip()
        if not text:
            raise RuntimeError("OpenClaw Gateway returned no JSON response.")

        candidates = [text]
        candidates.extend(
            line.strip()
            for line in reversed(text.splitlines())
            if line.strip().startswith(("{", "["))
        )
        data: Any = None
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                break
            except Exception as exc:
                last_error = exc
        if data is None:
            raise RuntimeError("Could not decode OpenClaw Gateway JSON.") from last_error

        if not isinstance(data, dict):
            raise RuntimeError("OpenClaw Gateway returned an unexpected JSON shape.")

        # Different OpenClaw CLI builds have wrapped RPC payloads slightly
        # differently. Peel common envelopes while preserving the wizard data.
        for key in ("result", "payload", "data"):
            nested = data.get(key)
            if isinstance(nested, dict) and (
                "done" in nested
                or "step" in nested
                or "sessionId" in nested
                or "status" in nested
            ):
                data = nested
                break
        return data

    def _rpc(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_ms: int = 120_000,
    ) -> dict[str, Any]:
        proc = self._run(
            "gateway",
            "call",
            method,
            "--url",
            self.gateway_url,
            "--token",
            self.gateway_token,
            "--params",
            json.dumps(params, separators=(",", ":")),
            "--json",
            "--timeout",
            str(timeout_ms),
            timeout=max(30.0, timeout_ms / 1000.0 + 10.0),
        )
        if proc.returncode != 0:
            detail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
            raise RuntimeError(detail[-4000:] or f"OpenClaw RPC {method} failed.")
        return self._decode_json(proc.stdout or "")

    def _start_temporary_gateway(self) -> None:
        if self.gateway_process is not None:
            return

        port = self._pick_port()
        token = secrets.token_urlsafe(32)
        self.gateway_url = f"ws://127.0.0.1:{port}"
        self.gateway_token = token

        log = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            prefix="jervis-openclaw-gateway-",
            suffix=".log",
            delete=False,
        )
        self._gateway_log = log
        self._gateway_log_path = Path(log.name)

        command, shell = self._command(
            "gateway",
            "run",
            "--allow-unconfigured",
            "--port",
            str(port),
            "--bind",
            "loopback",
            "--auth",
            "token",
            "--token",
            token,
        )
        self.gateway_process = subprocess.Popen(
            command,
            shell=shell,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )

    def _gateway_tail(self) -> str:
        path = self._gateway_log_path
        if not path or not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            return ""

    @staticmethod
    def _as_result(data: dict[str, Any]) -> WizardResult:
        return WizardResult(
            done=bool(data.get("done", False)),
            status=str(data.get("status", "running")),
            step=data.get("step") if isinstance(data.get("step"), dict) else None,
            error=str(data["error"]) if data.get("error") is not None else None,
        )

    def start(self) -> WizardResult:
        self._start_temporary_gateway()

        deadline = time.monotonic() + 30.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            proc = self.gateway_process
            if proc is not None and proc.poll() is not None:
                detail = self._gateway_tail()
                raise RuntimeError(
                    "Temporary OpenClaw Gateway exited before onboarding started.\n"
                    + detail
                )
            try:
                data = self._rpc(
                    "wizard.start",
                    {"mode": "local"},
                    timeout_ms=120_000,
                )
                session_id = data.get("sessionId")
                if not isinstance(session_id, str) or not session_id:
                    raise RuntimeError("OpenClaw wizard.start did not return a session ID.")
                self.session_id = session_id
                result = self._as_result(data)
                if result.done:
                    self.session_id = None
                return result
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "setup_admission_busy" in message or "wizard already running" in message:
                    raise
                time.sleep(0.25)

        detail = self._gateway_tail()
        raise RuntimeError(
            "OpenClaw Gateway did not become ready for the setup wizard."
            + (("\n" + detail) if detail else "")
        ) from last_error

    def next(self, step_id: str | None = None, value: Any = None) -> WizardResult:
        if not self.session_id:
            raise RuntimeError("OpenClaw setup wizard has not started.")
        params: dict[str, Any] = {"sessionId": self.session_id}
        if step_id is not None:
            params["answer"] = {"stepId": step_id, "value": value}
        data = self._rpc("wizard.next", params, timeout_ms=180_000)
        result = self._as_result(data)
        if result.done:
            self.session_id = None
        return result

    def cancel(self) -> None:
        if self.session_id:
            try:
                self._rpc(
                    "wizard.cancel",
                    {"sessionId": self.session_id},
                    timeout_ms=15_000,
                )
            except Exception:
                pass
            self.session_id = None

    def close(self) -> None:
        self.cancel()
        process = self.gateway_process
        self.gateway_process = None
        if process is not None and process.poll() is None:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        if self._gateway_log is not None:
            try:
                self._gateway_log.close()
            except Exception:
                pass
            self._gateway_log = None

        if self._gateway_log_path is not None:
            try:
                self._gateway_log_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._gateway_log_path = None
