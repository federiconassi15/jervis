from pathlib import Path

import jervis.openclaw_setup as setup
from jervis.install_plan import InstallPlan


def _base_plan(**changes):
    plan = InstallPlan(
        mode="server",
        source_kind="desktop",
        input_device=0,
        output_device=1,
        owner_name="Example",
        honorific="sir",
        passphrase="correct horse battery staple",
        openclaw_accept_risk=True,
    )
    for key, value in changes.items():
        setattr(plan, key, value)
    return plan


def test_find_openclaw_prefers_path(monkeypatch, tmp_path):
    executable = tmp_path / ("openclaw.cmd" if setup.platform.system() == "Windows" else "openclaw")
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(setup.shutil, "which", lambda name: str(executable) if name == "openclaw" else None)
    assert setup.find_openclaw() == executable


def test_doctor_uses_cli(monkeypatch):
    class Result:
        returncode = 0
        stdout = "healthy"
        stderr = ""

    monkeypatch.setattr(setup, "run", lambda *args, **kwargs: Result())
    ok, detail = setup.doctor(Path("openclaw"))
    assert ok
    assert detail == "healthy"


def test_openclaw_plan_hides_secrets_from_repr():
    plan = _base_plan(
        openclaw_auth="openai-api-key",
        openclaw_api_key="super-secret-provider-key",
        openclaw_gateway_auth="password",
        openclaw_gateway_secret="super-secret-gateway",
    )
    text = repr(plan)
    assert "super-secret-provider-key" not in text
    assert "super-secret-gateway" not in text


def test_openai_api_key_builds_hidden_noninteractive_onboarding():
    plan = _base_plan(
        openclaw_auth="openai-api-key",
        openclaw_api_key="secret",
    )
    args = setup._provider_onboard_args(plan)
    assert args[:3] == ["onboard", "--non-interactive", "--accept-risk"]
    assert "--auth-choice" in args
    assert "openai-api-key" in args
    assert "--openai-api-key" in args
    assert "--skip-ui" in args
    assert "--install-daemon" in args
    assert "--gateway-bind" in args
    assert "loopback" in args


def test_custom_provider_builds_full_onboarding_flags():
    plan = _base_plan(
        openclaw_auth="custom-api-key",
        openclaw_api_key="secret",
        openclaw_custom_base_url="https://llm.example.com/v1",
        openclaw_custom_model_id="foo-large",
        openclaw_custom_provider_id="example",
        openclaw_custom_compatibility="anthropic",
        openclaw_custom_image_input=True,
        openclaw_gateway_auth="token",
        openclaw_gateway_secret="12345678",
        openclaw_daemon_runtime="bun",
        openclaw_node_manager="pnpm",
        openclaw_setup_channels=True,
    )
    args = setup._provider_onboard_args(plan)
    assert "custom-api-key" in args
    assert "https://llm.example.com/v1" in args
    assert "foo-large" in args
    assert "example" in args
    assert "anthropic" in args
    assert "--custom-image-input" in args
    assert "--gateway-token" in args
    assert "12345678" in args
    assert "--daemon-runtime" in args and "bun" in args
    assert "--node-manager" in args and "pnpm" in args
    assert "--skip-channels" not in args


def test_oauth_routes_require_external_authorization():
    assert setup.needs_interactive_authorization(
        _base_plan(openclaw_auth="openai")
    )
    assert setup.needs_interactive_authorization(
        _base_plan(openclaw_auth="xai-oauth")
    )
    assert not setup.needs_interactive_authorization(
        _base_plan(openclaw_auth="anthropic-api-key", openclaw_api_key="secret")
    )


def test_openclaw_step_validation_requires_risk_and_provider_secret():
    plan = _base_plan(
        openclaw_auth="gemini-api-key",
        openclaw_accept_risk=False,
        openclaw_api_key="",
    )
    try:
        plan.validate_openclaw()
    except ValueError as exc:
        assert "Acknowledge" in str(exc)
    else:
        raise AssertionError("expected risk acknowledgement validation error")

    plan.openclaw_accept_risk = True
    try:
        plan.validate_openclaw()
    except ValueError as exc:
        assert "provider credential" in str(exc)
    else:
        raise AssertionError("expected provider credential validation error")


def test_configure_noninteractive_never_uses_raw_wizard(monkeypatch):
    plan = _base_plan(
        openclaw_auth="mistral-api-key",
        openclaw_api_key="secret",
    )
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cli: Path, *args, **kwargs):
        calls.append((cli, args, kwargs))
        return Result()

    monkeypatch.setattr(setup, "run", fake_run)
    setup.configure_noninteractive(Path("/tmp/openclaw"), plan)

    _cli, args, kwargs = calls[0]
    assert args[0] == "onboard"
    assert "--non-interactive" in args
    assert kwargs["interactive"] is False
