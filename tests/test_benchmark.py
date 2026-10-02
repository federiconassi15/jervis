from __future__ import annotations

from jervis.benchmark import format_report, run_benchmark
from jervis.paths import Paths


def test_benchmark_runs_in_isolated_paths(tmp_path):
    paths = Paths(
        root=tmp_path,
        config=tmp_path / "config",
        data=tmp_path / "data",
        logs=tmp_path / "logs",
        cache=tmp_path / "cache",
    )
    report = run_benchmark(iterations=5, history=5, paths=paths)
    assert report["iterations"] == 5
    assert report["synthetic"]["audio_analyze_us"]["count"] == 5
    assert report["synthetic"]["kv_roundtrip_ms"]["count"] == 5
    assert report["synthetic"]["context_snapshot_ms"]["count"] == 5
    assert "Jervis benchmark" in format_report(report)
