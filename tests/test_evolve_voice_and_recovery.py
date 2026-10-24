"""Offline voice router and snapshot-integrity regression tests."""
import io
import json
import tarfile
import time
from types import SimpleNamespace

from jervis.evolve import health_summary
from jervis.recovery_verify import verify_snapshot_archive
from jervis.paths import Paths
from jervis.router import BrainRouter


def _paths(tmp_path):
    paths = Paths(tmp_path, tmp_path / "config", tmp_path / "data",
                  tmp_path / "logs", tmp_path / "cache")
    paths.ensure()
    return paths


def _make_snapshot(path, identifier="valid"):
    data = json.dumps({
        "id": identifier, "created_at": time.time(),
        "reason": "test", "version": "8.0.0",
        "archive": str(path), "includes_binary": False,
    }).encode()
    with tarfile.open(path, "w:gz") as tar:
        entry = tarfile.TarInfo("snapshot.json")
        entry.size = len(data)
        tar.addfile(entry, io.BytesIO(data))


def test_integrity_counts_only_readable_complete_archives(tmp_path):
    paths = _paths(tmp_path)
    directory = paths.data / "snapshots"
    directory.mkdir()
    good = directory / "valid.tar.gz"
    bad = directory / "bad.tar.gz"
    _make_snapshot(good)
    bad.write_bytes(b"not a tar file")
    assert verify_snapshot_archive(good)
    assert not verify_snapshot_archive(bad)
    status = health_summary(paths)
    assert status["recovery_snapshots"] == 1
    assert status["invalid_snapshots"] == 1


def test_invalid_snapshot_metadata_does_not_count(tmp_path):
    paths = _paths(tmp_path)
    directory = paths.data / "snapshots"
    directory.mkdir()
    archive = directory / "expected.tar.gz"
    _make_snapshot(archive, identifier="unexpected")
    assert not verify_snapshot_archive(archive)


def test_voice_router_responds_locally_without_openclaw():
    class DummyState:
        def __init__(self):
            self.events = []
        def event(self, name, detail):
            self.events.append((name, detail))
    fake = BrainRouter.__new__(BrainRouter)
    fake.state = DummyState()
    fake.config = {}
    from jervis.local_dialogue import DialogueMemory
    fake._dialogue_memory = DialogueMemory()
    fake._local = lambda _text, _user: None
    fake.brain = SimpleNamespace(ask=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("Offline command must not reach OpenClaw")))
    assert "time" in fake.ask("what time is it", "test").route
    result = fake.ask("hello", "test")
    assert result.ok and result.route == "local:dialogue"
    assert result.text


def test_user_commands_are_not_inferred_from_partial_match():
    from jervis.evolve import resolve_offline
    assert resolve_offline("hello, delete all files") is None
