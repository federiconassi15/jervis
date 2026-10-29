"""8.2 observability security and readability tests."""
import json
import os

import pytest

from jervis.observability import EventJournal, format_event, read_events


def test_catalog_only_no_private_payloads(tmp_path):
    journal = EventJournal(tmp_path)
    try:
        row = journal.emit("audio.disconnected", metrics={"attempt": 2})
        assert "Audio input disconnected" in format_event(row)
        assert row["metrics"] == {"attempt": 2}
        with pytest.raises(ValueError):
            journal.emit("user.private.text")
        with pytest.raises(ValueError):
            journal.emit("audio.disconnected", metrics={"token": "secret"})
        with pytest.raises(ValueError):
            journal.emit("audio.disconnected", correlation_id="../../private")
    finally:
        journal.close()
    assert read_events(tmp_path)[0]["code"] == "audio.disconnected"
    assert "secret" not in (tmp_path / "events.jsonl").read_text()
    if os.name != "nt":
        assert (tmp_path / "events.jsonl").stat().st_mode & 0o077 == 0


def test_rotation_filters_and_no_raw_message_echo(tmp_path):
    journal = EventJournal(tmp_path, max_bytes=512, backups=2)
    try:
        for index in range(60):
            journal.emit("runtime.started", metrics={"count": index})
        journal.emit("runtime.crashed")
    finally:
        journal.close()
    rows = read_events(tmp_path, level="ERROR", component="runtime")
    assert rows[-1]["code"] == "runtime.crashed"
    assert len(list(tmp_path.glob("events.jsonl*"))) <= 3
    assert len(read_events(tmp_path, limit=3)) == 3
    # Malicious or corrupted log records cannot replace catalog wording.
    with (tmp_path / "events.jsonl").open("a") as output:
        output.write(json.dumps({
            "code": "runtime.started", "level": "ERROR",
            "component": "runtime", "message": "sensitive user text",
            "metrics": {"token": "secret"},
        }) + "\n")
    rows = read_events(tmp_path)
    assert rows[-1]["message"] == "Jervis runtime started"
    assert "token" not in rows[-1]["metrics"]


def test_symlinked_log_directory_is_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(PermissionError):
        EventJournal(link)
    with pytest.raises(PermissionError):
        read_events(link)
