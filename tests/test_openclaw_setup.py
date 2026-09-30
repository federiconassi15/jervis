from pathlib import Path

import jervis.openclaw_setup as setup


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
