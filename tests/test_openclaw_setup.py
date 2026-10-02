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
        openclaw_setup="wizard",
    )
    for key, value in changes.items():
        setattr(plan, key, value)
    return plan


def test_find_openclaw_prefers_path(monkeypatch, tmp_path):
    executable = tmp_path / (
        "openclaw.cmd" if setup.platform.system() == "Windows" else "openclaw"
    )
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        setup.shutil,
        "which",
        lambda name: str(executable) if name == "openclaw" else None,
    )
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


def test_openclaw_plan_accepts_upstream_wizard_mode():
    plan = _base_plan(openclaw_setup="wizard")
    plan.validate_openclaw()


def test_openclaw_plan_accepts_configure_later():
    plan = _base_plan(openclaw_setup="later")
    plan.validate_openclaw()


def test_openclaw_plan_rejects_unknown_setup_mode():
    plan = _base_plan(openclaw_setup="provider-specific")
    try:
        plan.validate_openclaw()
    except ValueError as exc:
        assert "OpenClaw" in str(exc)
    else:
        raise AssertionError("expected invalid OpenClaw setup mode to fail")


def test_openclaw_plan_has_no_provider_secret_fields():
    plan = _base_plan()
    fields = set(plan.__dataclass_fields__)
    assert "openclaw_api_key" not in fields
    assert "openclaw_gateway_secret" not in fields
    assert "openclaw_auth" not in fields
