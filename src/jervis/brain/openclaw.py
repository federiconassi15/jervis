from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
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


def _response_text(data: object) -> str:
    if not isinstance(data, dict):
        return ""

    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for piece in content:
                if not isinstance(piece, dict):
                    continue
                text = piece.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
    return "\n".join(parts).strip()


class OpenClawBrain:
    def __init__(
        self,
        agent: str = "main",
        timeout: int = 60,
        thinking: str = "low",
        *,
        gateway_http: bool = True,
        gateway_url: str = "http://127.0.0.1:18789",
        gateway_retry_seconds: int = 60,
    ) -> None:
        self.agent = agent
        self.timeout = int(timeout)
        self.thinking = thinking
        self.gateway_http = bool(gateway_http)
        self.gateway_url = gateway_url.rstrip("/")
        self.gateway_retry_seconds = max(5, int(gateway_retry_seconds))
        self._cli = find_openclaw()
        self._cli_checked_at = time.monotonic()
        self._http_disabled_until = 0.0
        self.last_transport = "none"

    @property
    def cli(self) -> Path | None:
        if self._cli is not None and self._cli.exists():
            return self._cli
        if time.monotonic() - self._cli_checked_at >= 30.0:
            self._cli = find_openclaw()
            self._cli_checked_at = time.monotonic()
        return self._cli

    @property
    def available(self) -> bool:
        return self.cli is not None or self.gateway_http

    @staticmethod
    def _gateway_token() -> str | None:
        for name in (
            "JERVIS_OPENCLAW_TOKEN",
            "OPENCLAW_GATEWAY_TOKEN",
            "OPENCLAW_GATEWAY_PASSWORD",
        ):
            value = os.environ.get(name, "").strip()
            if value:
                return value
        return None

    def _ask_http(self, message: str, session_key: str) -> BrainReply | None:
        if not self.gateway_http or time.monotonic() < self._http_disabled_until:
            return None

        body = json.dumps(
            {
                "model": "openclaw",
                "input": message,
                "user": session_key,
                "stream": False,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-openclaw-agent-id": self.agent,
            "x-openclaw-session-key": session_key,
        }
        token = self._gateway_token()
        if token:
            headers["Authorization"] = "Bearer " + token

        request = urllib.request.Request(
            self.gateway_url + "/v1/responses",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403, 404, 405}:
                self._http_disabled_until = (
                    time.monotonic() + self.gateway_retry_seconds
                )
                return None
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                detail = str(payload.get("error", {}).get("message") or "")
            except Exception:
                detail = ""
            return BrainReply(False, "", detail or "OpenClaw Gateway HTTP failed")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            self._http_disabled_until = time.monotonic() + self.gateway_retry_seconds
            return None

        text = _response_text(data)
        self.last_transport = "gateway-http"
        return BrainReply(
            bool(text),
            text,
            "" if text else "OpenClaw Gateway returned no final text",
        )

    def _ask_cli(
        self,
        message: str,
        session_key: str,
        thinking: str,
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
            thinking,
            "--timeout",
            str(self.timeout),
            "--json",
        ]
        try:
            proc = _run_cli(cli, args, self.timeout + 10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BrainReply(False, "", str(exc))

        self.last_transport = "cli"
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

    def ask(
        self,
        message: str,
        session_key: str,
        thinking: str | None = None,
    ) -> BrainReply:
        selected_thinking = thinking or self.thinking

        # The Gateway Responses API has lower overhead than a fresh CLI process.
        # Keep deep/high reasoning on the CLI because the CLI exposes the explicit
        # --thinking control while the compatibility HTTP surface does not.
        if selected_thinking in {"off", "minimal", "low"}:
            reply = self._ask_http(message, session_key)
            if reply is not None:
                return reply

        return self._ask_cli(message, session_key, selected_thinking)

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
