from __future__ import annotations

import json
from pathlib import Path

import jervis.snapshots as snapshots_module
from jervis.backup import create_backup, restore_backup
from jervis.benchmark import run_benchmark
from jervis.lifecycle import begin_runtime, end_runtime, inspect_runtime
from jervis.migrations import CURRENT_CONFIG_SCHEMA, migrate_config
from jervis.paths import Paths
from jervis.snapshots import create_snapshot, list_snapshots, restore_snapshot
from jervis.updater import _checksums


class _FakeAdapter:
    def service_installed(self):
        return False

    def stop_service(self):
        pass

    def start_service(self):
        pass


def _paths(tmp_path: Path) -> Paths:
    paths = Paths(
        root=tmp_path,
        config=tmp_path / "config",
        data=tmp_path / "data",
        logs=tmp_path / "logs",
        cache=tmp_path / "cache",
    )
    paths.ensure()
    return paths


def test_snapshot_roundtrip_restores_mutable_state(monkeypatch, tmp_path):
    paths = _paths(tmp_path)
    monkeypatch.setattr(snapshots_module, "current_platform", lambda: _FakeAdapter())

    config = paths.config / "config.json"
    config.write_text('{"value":"before"}\n', encoding="utf-8")
    db = paths.data / "state.txt"
    db.write_text("before\n", encoding="utf-8")

    model = paths.data / "models" / "speaker.onnx"
    model.parent.mkdir(parents=True)
    model.write_text("keep-current-model", encoding="utf-8")

    snap = create_snapshot("unit-test", paths=paths)
    config.write_text('{"value":"after"}\n', encoding="utf-8")
    db.write_text("after\n", encoding="utf-8")
    model.write_text("newer-model", encoding="utf-8")

    restore_snapshot(snap.id, paths=paths, make_guard=False, restore_binary=False)

    assert "before" in config.read_text(encoding="utf-8")
    assert db.read_text(encoding="utf-8") == "before\n"
    assert model.read_text(encoding="utf-8") == "newer-model"
    assert list_snapshots(paths=paths)


def test_backup_roundtrip(monkeypatch, tmp_path):
    paths = _paths(tmp_path)
    monkeypatch.setattr(snapshots_module, "current_platform", lambda: _FakeAdapter())
    value = paths.data / "value.txt"
    value.write_text("original", encoding="utf-8")

    backup = create_backup(tmp_path / "backup.tar.gz", paths=paths)
    value.write_text("changed", encoding="utf-8")
    restore_backup(backup, paths=paths)

    assert value.read_text(encoding="utf-8") == "original"


def test_config_migration_framework_adds_recovery_defaults():
    migrated, changes = migrate_config({"schema": 1})
    assert migrated["schema"] == CURRENT_CONFIG_SCHEMA
    assert migrated["recovery"]["auto_snapshot"] is True
    assert changes


def test_crash_marker_tracks_unclean_then_clean(tmp_path):
    paths = _paths(tmp_path)
    first = begin_runtime(paths)
    assert first.previous_unclean is False

    unclean = inspect_runtime(paths)
    assert unclean.previous_unclean is True
    assert unclean.consecutive_crashes == 1

    end_runtime(paths)
    clean = inspect_runtime(paths)
    assert clean.previous_unclean is False
    assert clean.consecutive_crashes == 0


def test_checksum_parser():
    digest = "a" * 64
    parsed = _checksums(digest + "  jervis-linux-x64\n")
    assert parsed["jervis-linux-x64"] == digest


def test_benchmark_history_is_persisted(tmp_path):
    paths = _paths(tmp_path)
    report = run_benchmark(iterations=5, history=5, paths=paths)
    history = paths.data / "benchmark-history.jsonl"
    assert history.exists()
    row = json.loads(history.read_text(encoding="utf-8").splitlines()[-1])
    assert row["jervis_version"] == report["jervis_version"]
