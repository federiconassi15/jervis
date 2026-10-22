"""Adversarial release-gate tests for Jervis 8's platform-neutral terminal path.

Mocks deliberately prevent changes to host audio, filesystem, and services.
The same suite runs on Linux, Windows, and macOS through the existing CI matrix.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from jervis import simple_ui


def answers(*items):
    stream = iter(items)
    return lambda _prompt: next(stream)


@pytest.mark.parametrize("bad", ["0", "-1", "9999999999999999999999", "1.5", "one", "１", "²", "0x1", " ", "1x"])
def test_choice_rejects_invalid_or_ambiguous_selection(bad, capsys):
    result = simple_ui._choice("Choose", [("A", "a"), ("B", "b")], 2, answers(bad, "1"))
    assert result == "a"
    assert "Enter one of the displayed numbers" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["q", "Q", "quit", "QUIT", "cancel", " CANCEL "])
def test_choice_cancel_variations(value):
    with pytest.raises(simple_ui.Cancelled):
        simple_ui._choice("Choose", [("A", "a")], 1, answers(value))


@pytest.mark.parametrize("value", ["q", "QUIT", " Cancel "])
def test_confirmation_cancel_variations(value):
    with pytest.raises(simple_ui.Cancelled):
        simple_ui._yes_no("Proceed?", default=False, ask=answers(value))


@pytest.mark.parametrize("invalid_default,options", [(0, [("A", "a")]), (2, [("A", "a")]), (1, [])])
def test_choice_bad_internal_default_fails_closed(invalid_default, options):
    with pytest.raises(ValueError):
        simple_ui._choice("Choose", options, invalid_default, answers(""))


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(False, False), (False, True), (True, False)])
def test_interactive_setup_requires_both_ttys(monkeypatch, stdin_tty, stdout_tty):
    monkeypatch.setattr(simple_ui.sys, "stdin", SimpleNamespace(isatty=lambda: stdin_tty))
    monkeypatch.setattr(simple_ui.sys, "stdout", SimpleNamespace(isatty=lambda: stdout_tty))
    with pytest.raises(RuntimeError, match="needs a terminal"):
        simple_ui._terminal_required()


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(False, False), (False, True), (True, False)])
def test_home_never_reads_from_pipe(monkeypatch, stdin_tty, stdout_tty):
    monkeypatch.setattr(simple_ui.sys, "stdin", SimpleNamespace(isatty=lambda: stdin_tty))
    monkeypatch.setattr(simple_ui.sys, "stdout", SimpleNamespace(isatty=lambda: stdout_tty, write=lambda s: len(s), flush=lambda: None))
    monkeypatch.setattr(simple_ui, "_choice", lambda *a, **kw: pytest.fail("home tried to read input"))
    assert simple_ui.home() == 0


@pytest.mark.parametrize("failure", [OSError("no adb"), subprocess.TimeoutExpired("adb", 5)])
def test_android_adb_failure_is_nonfatal_and_does_not_select_unauthorized(monkeypatch, failure):
    import jervis.prereqs as prereqs
    monkeypatch.setattr(prereqs, "find_adb", lambda: "adb")
    def fail(*_args, **_kwargs):
        raise failure
    monkeypatch.setattr(simple_ui.subprocess, "run", fail)
    assert simple_ui._android_serial(answers()) is None


def test_android_only_authorized_devices_are_listed(monkeypatch):
    import jervis.prereqs as prereqs
    monkeypatch.setattr(prereqs, "find_adb", lambda: "adb")
    output = "List of devices attached\nabc\tunauthorized\nready\tdevice\noffline\toffline\n"
    monkeypatch.setattr(simple_ui.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=output))
    assert simple_ui._android_serial(answers("")) == "ready"


def test_audio_enumeration_error_is_explained_without_installing(monkeypatch):
    monkeypatch.setattr(simple_ui, "_devices", lambda: (_ for _ in ()).throw(OSError("driver")))
    with pytest.raises(RuntimeError, match="Could not list audio devices"):
        simple_ui.make_plan(ask=answers("", "", ""), secret=answers())


def test_no_microphone_fails_before_owner_creation(monkeypatch):
    monkeypatch.setattr(simple_ui, "_devices", lambda: ([], [SimpleNamespace(index=4, name="Speaker", hostapi="test", outputs=2)], None, 4))
    with pytest.raises(RuntimeError, match="microphone"):
        simple_ui.make_plan(ask=answers("", "", ""), secret=answers())


@pytest.mark.parametrize("error", [RuntimeError("disk failure"), ValueError("invalid plan"), OSError("permission denied")])
def test_install_engine_failure_never_reports_success_and_erases_secret(monkeypatch, capsys, error):
    import jervis.install_engine as engine
    plan = SimpleNamespace(
        mode="desktop", source_kind="desktop", input_device=1, output_device=2,
        install_openclaw=False, openclaw_setup="later", owner_name="Test",
        start_at_boot=False, passphrase="secret-passphrase",
    )
    monkeypatch.setattr(simple_ui, "_terminal_required", lambda: None)
    monkeypatch.setattr(simple_ui, "make_plan", lambda: plan)
    monkeypatch.setattr(simple_ui, "_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(simple_ui, "_launcher", lambda: "jervis")
    def fail(*_args, **_kwargs):
        raise error
    monkeypatch.setattr(engine, "run_install", fail)
    assert simple_ui.install() == 1
    captured = capsys.readouterr()
    assert "installation complete" not in captured.out.lower()
    assert "Setup stopped" in captured.err
    assert plan.passphrase == ""


@pytest.mark.parametrize("answer", [False])
def test_review_rejection_never_invokes_engine(monkeypatch, capsys, answer):
    import jervis.install_engine as engine
    plan = SimpleNamespace(
        mode="desktop", source_kind="desktop", input_device=1, output_device=2,
        install_openclaw=False, openclaw_setup="later", owner_name="Test",
        start_at_boot=False, passphrase="secret-passphrase",
    )
    monkeypatch.setattr(simple_ui, "_terminal_required", lambda: None)
    monkeypatch.setattr(simple_ui, "make_plan", lambda: plan)
    monkeypatch.setattr(simple_ui, "_yes_no", lambda *a, **k: answer)
    monkeypatch.setattr(engine, "run_install", lambda *a, **k: pytest.fail("engine executed without consent"))
    assert simple_ui.install() == 0
    assert "No changes made" in capsys.readouterr().out


@pytest.mark.parametrize("path_kind", ["missing"])
def test_launcher_missing_override_does_not_fallback(monkeypatch, tmp_path, path_kind):
    monkeypatch.setenv("JERVIS_LAUNCHER_PATH", str(tmp_path / path_kind))
    monkeypatch.setattr(simple_ui.shutil, "which", lambda *_: pytest.fail("unexpected fallback"))
    with pytest.raises(RuntimeError, match="does not exist"):
        simple_ui._launcher()


def test_secret_mismatch_retries_without_disclosing_secret(capsys):
    name, password = simple_ui._owner(answers("Owner"), answers("firstsecret", "wrongsecret", "secondsecret", "secondsecret"))
    assert name == "Owner"
    assert password == "secondsecret"
    printed = capsys.readouterr().out
    assert "firstsecret" not in printed
    assert "secondsecret" not in printed
