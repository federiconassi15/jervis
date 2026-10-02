from __future__ import annotations

import os
import platform
import secrets
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from .openclaw_providers import provider

Progress = Callable[[str], None]


def find_openclaw() -> Path | None:
    found = shutil.which("openclaw")
    if found:
        return Path(found)

    home = Path.home()
    candidates: list[Path] = []
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        candidates += [
            appdata / "npm" / "openclaw.cmd",
            appdata / "npm" / "openclaw.exe",
        ]
    else:
        candidates += [
            home / ".npm-global" / "bin" / "openclaw",
            home / ".local" / "bin" / "openclaw",
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
        except (OSError, subprocess.TimeoutExpired):
            pass

    return next((path for path in candidates if path.exists()), None)


def run(
    cli: Path,
    *args: str,
    interactive: bool = True,
    timeout: float | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    kwargs = {"check": False, "text": True, "timeout": timeout}
    if env_extra:
        kwargs["env"] = {**os.environ, **env_extra}
    if not interactive:
        kwargs["capture_output"] = True

    if platform.system() == "Windows" and cli.suffix.lower() in {".cmd", ".bat"}:
        command = subprocess.list2cmdline([str(cli), *args])
        return subprocess.run(command, shell=True, **kwargs)

    return subprocess.run([str(cli), *args], **kwargs)


def install_official(progress: Progress) -> Path:
    progress("Installing OpenClaw quietly")
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
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-NoOnboard",
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
        raise RuntimeError("OpenClaw installation failed: " + detail)

    cli = find_openclaw()
    if not cli:
        raise RuntimeError(
            "OpenClaw installed successfully, but its command is not visible in this terminal yet."
        )
    return cli


def doctor(cli: Path) -> tuple[bool, str]:
    try:
        proc = run(cli, "doctor", interactive=False, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "OpenClaw doctor timed out"
    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, detail[-3000:]


def _base_onboard_args(plan) -> list[str]:
    args = [
        "onboard",
        "--non-interactive",
        "--accept-risk",
        "--mode",
        "local",
        "--agent-name",
        plan.openclaw_agent_name.strip() or "main",
        "--secret-input-mode",
        "plaintext",
        "--gateway-bind",
        plan.openclaw_gateway_bind,
        "--daemon-runtime",
        plan.openclaw_daemon_runtime,
        "--node-manager",
        plan.openclaw_node_manager,
        "--skip-ui",
        "--skip-health",
        "--suppress-gateway-token-output",
    ]

    if plan.openclaw_install_daemon:
        args.append("--install-daemon")
    else:
        args.append("--skip-daemon")
    if not plan.openclaw_setup_skills:
        args.append("--skip-skills")
    if not plan.openclaw_setup_hooks:
        args.append("--skip-hooks")
    if not plan.openclaw_setup_channels:
        args.append("--skip-channels")
    if not plan.openclaw_setup_search:
        args.append("--skip-search")

    if plan.openclaw_gateway_auth == "token":
        args += [
            "--gateway-auth",
            "token",
            "--gateway-token",
            plan.openclaw_gateway_secret,
        ]
    elif plan.openclaw_gateway_auth == "password":
        args += [
            "--gateway-auth",
            "password",
            "--gateway-password",
            plan.openclaw_gateway_secret,
        ]

    return args


def _provider_environment(plan) -> dict[str, str]:
    key = plan.openclaw_api_key.strip()
    if not key:
        return {}

    if plan.openclaw_auth == "custom-api-key":
        return {"CUSTOM_API_KEY": key}
    if plan.openclaw_auth == "universal-provider":
        env_name = plan.openclaw_universal_credential_env.strip()
        return {env_name: key} if env_name else {}

    spec = provider(plan.openclaw_auth)
    if spec and spec.credential_env:
        return {spec.credential_env: key}
    return {}


def _provider_plugin(plan) -> str:
    if plan.openclaw_auth == "universal-provider":
        return plan.openclaw_universal_plugin.strip()
    spec = provider(plan.openclaw_auth)
    return spec.plugin if spec and spec.plugin else ""


def _plugin_id(package: str) -> str:
    name = package.rsplit("/", 1)[-1]
    return name.removesuffix("-provider")


def _ensure_provider_plugin(cli: Path, plan) -> None:
    plugin = _provider_plugin(plan)
    if not plugin:
        return
    if not plan.openclaw_accept_plugin_capabilities:
        raise RuntimeError(
            "The selected OpenClaw provider requires plugin capability approval."
        )

    proc = run(
        cli,
        "plugins",
        "install",
        plugin,
        "--accept-capabilities",
        interactive=False,
        timeout=180,
    )
    if proc.returncode == 0:
        return

    # An already-installed official plugin may reject a second install. Enabling
    # it with explicit capability consent is the safe idempotent fallback.
    enable = run(
        cli,
        "plugins",
        "enable",
        _plugin_id(plugin),
        "--accept-capabilities",
        interactive=False,
        timeout=60,
    )
    if enable.returncode == 0:
        return

    detail = ((proc.stderr or "") + (proc.stdout or "")).strip()[-3000:]
    raise RuntimeError(
        "OpenClaw provider plugin installation failed"
        + (": " + detail if detail else ".")
    )


def _provider_onboard_args(plan) -> list[str]:
    args = _base_onboard_args(plan)
    auth = plan.openclaw_auth

    if auth == "custom-api-key":
        args += [
            "--auth-choice",
            "custom-api-key",
            "--custom-base-url",
            plan.openclaw_custom_base_url.strip(),
            "--custom-model-id",
            plan.openclaw_custom_model_id.strip(),
            "--custom-compatibility",
            plan.openclaw_custom_compatibility,
        ]
        provider_id = plan.openclaw_custom_provider_id.strip()
        if provider_id:
            args += ["--custom-provider-id", provider_id]
        args.append(
            "--custom-image-input"
            if plan.openclaw_custom_image_input
            else "--custom-text-input"
        )
        return args

    if auth == "universal-provider":
        args += [
            "--auth-choice",
            plan.openclaw_universal_auth_choice.strip(),
        ]
        if plan.openclaw_custom_base_url.strip():
            args += ["--custom-base-url", plan.openclaw_custom_base_url.strip()]
        if plan.openclaw_custom_model_id.strip():
            args += ["--custom-model-id", plan.openclaw_custom_model_id.strip()]
        return args

    spec = provider(auth)
    if spec is None:
        raise ValueError("Unknown OpenClaw provider.")
    if spec.interactive:
        raise ValueError("OpenClaw auth mode requires external authorization.")

    args += ["--auth-choice", spec.auth_choice]

    if spec.requires_base_url:
        args += ["--custom-base-url", plan.openclaw_custom_base_url.strip()]
    if spec.local and plan.openclaw_custom_model_id.strip():
        args += ["--custom-model-id", plan.openclaw_custom_model_id.strip()]

    return args


def needs_interactive_authorization(plan) -> bool:
    spec = provider(plan.openclaw_auth)
    return bool(spec and spec.interactive)


def _redact_detail(detail: str, plan) -> str:
    for secret in (plan.openclaw_api_key, plan.openclaw_gateway_secret):
        if secret:
            detail = detail.replace(secret, "[REDACTED]")
    return detail


def configure_noninteractive(cli: Path, plan) -> None:
    """Run any non-OAuth OpenClaw provider setup behind Jervis."""
    if plan.openclaw_auth == "later":
        return
    if needs_interactive_authorization(plan):
        return

    _ensure_provider_plugin(cli, plan)
    proc = run(
        cli,
        *_provider_onboard_args(plan),
        interactive=False,
        timeout=300,
        env_extra=_provider_environment(plan),
    )
    if proc.returncode != 0:
        detail = ((proc.stderr or "") + (proc.stdout or "")).strip()[-3000:]
        detail = _redact_detail(detail, plan)
        if not detail:
            detail = "OpenClaw onboarding returned a non-zero exit code."
        raise RuntimeError("OpenClaw hidden onboarding failed: " + detail)


def _config_set(cli: Path, key: str, value: str) -> None:
    proc = run(
        cli,
        "config",
        "set",
        key,
        value,
        interactive=False,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError("OpenClaw configuration update failed for " + key + ".")


def _apply_gateway_after_auth(cli: Path, plan) -> None:
    _config_set(cli, "gateway.mode", "local")
    _config_set(cli, "gateway.bind", plan.openclaw_gateway_bind)

    if plan.openclaw_gateway_auth == "password":
        _config_set(cli, "gateway.auth.mode", "password")
        _config_set(cli, "gateway.auth.password", plan.openclaw_gateway_secret)
    else:
        token = (
            plan.openclaw_gateway_secret
            if plan.openclaw_gateway_auth == "token"
            else secrets.token_urlsafe(32)
        )
        _config_set(cli, "gateway.auth.mode", "token")
        _config_set(cli, "gateway.auth.token", token)

    if plan.openclaw_install_daemon:
        gateway = run(
            cli,
            "gateway",
            "install",
            "--runtime",
            plan.openclaw_daemon_runtime,
            "--force",
            interactive=False,
            timeout=120,
        )
        if gateway.returncode != 0:
            raise RuntimeError("OpenClaw gateway installation did not complete.")


def configure_interactive_authorization(cli: Path, plan) -> None:
    """Handle external provider authorization, then apply Jervis choices."""
    auth_mode = plan.openclaw_auth
    if auth_mode == "openai":
        method = "device-code" if plan.mode == "server" else "oauth"
        proc = run(
            cli,
            "models",
            "auth",
            "login",
            "--provider",
            "openai",
            "--method",
            method,
            "--set-default",
            interactive=True,
        )
        if proc.returncode != 0:
            raise RuntimeError("ChatGPT/Codex sign-in did not complete.")
    elif auth_mode == "xai-oauth":
        proc = run(
            cli,
            "models",
            "auth",
            "login",
            "--provider",
            "xai",
            "--method",
            "oauth",
            "--set-default",
            interactive=True,
        )
        if proc.returncode != 0:
            raise RuntimeError("xAI/Grok sign-in did not complete.")
    else:
        raise RuntimeError(
            "This provider uses an external authorization route that Jervis "
            "does not yet have a provider-specific authorization adapter for."
        )

    _apply_gateway_after_auth(cli, plan)


# Compatibility alias for older callers.
def configure_mode(cli: Path, mode: str, auth_mode: str) -> None:
    class _CompatPlan:
        pass

    plan = _CompatPlan()
    plan.mode = mode
    plan.openclaw_auth = auth_mode
    plan.openclaw_gateway_bind = "loopback"
    plan.openclaw_gateway_auth = "generated-token"
    plan.openclaw_gateway_secret = ""
    plan.openclaw_install_daemon = True
    plan.openclaw_daemon_runtime = "node"
    configure_interactive_authorization(cli, plan)
