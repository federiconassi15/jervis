from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from jervis import simple_ui


@dataclass
class Device:
    index: int
    name: str
    hostapi: str
    inputs: int
    outputs: int


def _answers(*values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_choice_uses_visible_default_and_retries_invalid(capsys):
    picked = simple_ui._choice(
        "Mode", [("Desktop", "desktop"), ("Server", "server")],
        2, _answers("none", "3", ""),
    )
    assert picked == "server"
    assert "default" in capsys.readouterr().out


def test_choice_cancel_never_applies():
    with pytest.raises(simple_ui.Cancelled):
        simple_ui._choice("Mode", [("Desktop", "desktop")], 1, _answers("q"))


def test_yes_no_is_explicit_and_defaults():
    assert simple_ui._yes_no("Autostart?", default=True, ask=_answers(""))
    assert not simple_ui._yes_no("Apply?", default=False, ask=_answers(""))
    assert simple_ui._yes_no("Apply?", default=False, ask=_answers("yes"))


def test_make_plan_is_plain_and_preserves_existing_engine_fields(monkeypatch):
    monkeypatch.setattr(
        simple_ui, "_devices",
        lambda: (
            [Device(4, "Mic", "Core", 1, 0)],
            [Device(8, "Speaker", "Core", 0, 2)],
            4, 8,
        ),
    )
    plan = simple_ui.make_plan(
        ask=_answers("2", "2", "1", "", "", "Alex", "2", "n"),
        secret=_answers("password123", "password123"),
    )
    assert plan.mode == "server"
    assert plan.openclaw_setup == "later"
    assert plan.install_openclaw
    assert plan.input_device == 4
    assert plan.output_device == 8
    assert plan.owner_name == "Alex"
    assert plan.honorific == "maam"
    assert not plan.start_at_boot
    assert plan.passphrase == "password123"


def test_empty_output_devices_fail_before_install(monkeypatch):
    monkeypatch.setattr(simple_ui, "_devices", lambda: ([], [], None, None))
    with pytest.raises(RuntimeError, match="speaker"):
        simple_ui.make_plan(ask=_answers("", "", "2"), secret=_answers())


def test_install_non_tty_fails_closed(monkeypatch, capsys):
    def no_tty():
        raise RuntimeError("Interactive setup needs a terminal.")
    monkeypatch.setattr(simple_ui, "_terminal_required", no_tty)
    assert simple_ui.install() == 1
    assert "needs a terminal" in capsys.readouterr().err


def test_home_non_tty_only_prints_commands(monkeypatch, capsys):
    monkeypatch.setattr(simple_ui.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    assert simple_ui.home() == 0
    out = capsys.readouterr().out
    assert "jervis status" in out
    assert "jervis --help" in out


def test_launcher_override_must_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("JERVIS_LAUNCHER_PATH", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="does not exist"):
        simple_ui._launcher()


def test_cli_default_does_not_load_legacy_tuis(monkeypatch):
    from jervis import cli
    called = []
    monkeypatch.setattr(cli, "run_home", lambda: called.append("home") or 0)
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 0
    assert called == ["home"]


def test_tui_command_is_simple_compatibility_alias(monkeypatch):
    from jervis import cli
    called = []
    monkeypatch.setattr(cli, "run_home", lambda: called.append("simple") or 0)
    with pytest.raises(SystemExit):
        cli.main(["tui"])
    assert called == ["simple"]

def test_reinstall_does_not_uninstall_before_confirmed_setup(monkeypatch):
    from jervis import cli
    calls = []
    monkeypatch.setattr(cli, "install", lambda: calls.append("install") or 130)
    monkeypatch.setattr(
        cli, "uninstall", lambda **_kwargs: calls.append("uninstall")
    )
    with pytest.raises(SystemExit) as exc:
        cli.main(["reinstall"])
    assert exc.value.code == 130
    assert calls == ["install"]
