"""HyperCore latency window and local routing."""
import math

import pytest

from jervis.hypercore import FastRouter, LatencyWindow, benchmark_fast_path


def test_only_explicit_local_intents_are_handled():
    router = FastRouter()
    assert router.respond("hello")
    assert router.respond("time")
    assert router.respond("delete files") is None
    assert router.latency.snapshot()["count"] == 3


def test_latency_window_is_bounded_and_has_tail_statistics():
    window = LatencyWindow(4)
    for value in (1, 2, 3, 4, 5):
        window.record(value)
    report = window.snapshot()
    assert report["count"] == 4
    assert report["median_ms"] == 3.5
    assert report["p95_ms"] == 5
    with pytest.raises(ValueError):
        window.record(float("nan"))


def test_benchmark_reports_real_monotonic_measurements():
    result = benchmark_fast_path(iterations=50)
    assert result["iterations"] == 50
    assert 0 <= result["median_ms"] <= result["p95_ms"] <= result["max_ms"]
    assert result["scope"].startswith("offline")


def test_benchmark_rejects_unbounded_iterations():
    with pytest.raises(ValueError):
        benchmark_fast_path(iterations=999999)
