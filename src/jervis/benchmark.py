from __future__ import annotations

import json
import math
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from .audio.processing import analyze
from .fast import NATIVE_AVAILABLE, backend_name
from .paths import Paths
from .state import State
from .version import __version__


def _stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * fraction
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return ordered[low]
        weight = position - low
        return ordered[low] * (1.0 - weight) + ordered[high] * weight

    return {
        "count": len(ordered),
        "min": min(ordered),
        "median": statistics.median(ordered),
        "p95": percentile(0.95),
        "mean": statistics.fmean(ordered),
        "max": max(ordered),
    }


def _time_many(function, iterations: int, scale: float = 1000.0) -> dict[str, float | int]:
    values: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        function()
        elapsed = time.perf_counter_ns() - started
        values.append(elapsed / scale)
    return _stats(values)


def _synthetic_frame() -> np.ndarray:
    samples = 480
    phase = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    return (np.sin(phase * 7.0) * 0.05).astype(np.float32)


def _state_bench(paths: Paths, iterations: int) -> dict[str, Any]:
    paths.cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jervis-bench-", dir=paths.cache) as directory:
        state = State(Path(directory) / "benchmark.sqlite3")
        try:
            state.upsert_user("bench-user", "Benchmark User", "sir", "owner")
            for index in range(6):
                state.remember("bench-user", "memory-" + str(index), "value-" + str(index))
            for index in range(8):
                state.dialogue("user", "benchmark dialogue " + str(index), "bench-user")
            state.set_kv("brain.agent.bench-user", "main")

            counter = 0

            def kv_roundtrip() -> None:
                nonlocal counter
                counter += 1
                state.set_kv("benchmark.counter", counter)
                state.get_kv("benchmark.counter")

            def snapshot() -> None:
                state.context_snapshot(
                    "bench-user",
                    memory_limit=6,
                    dialogue_limit=0,
                )

            return {
                "kv_roundtrip_ms": _time_many(kv_roundtrip, iterations, 1_000_000.0),
                "context_snapshot_ms": _time_many(snapshot, iterations, 1_000_000.0),
            }
        finally:
            state.close()


def _live_metrics(database: Path, history: int) -> dict[str, Any]:
    if not database.exists():
        return {}

    uri = "file:" + database.resolve().as_posix() + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=1.0)
    except sqlite3.Error:
        return {}

    try:
        found = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metrics'"
        ).fetchone()
        if found is None:
            return {}

        output: dict[str, Any] = {}
        for name in ("inference_ms", "brain_ms", "command_to_reply_ms"):
            rows = connection.execute(
                "SELECT value FROM metrics WHERE name=? "
                "ORDER BY id DESC LIMIT ?",
                (name, max(1, int(history))),
            ).fetchall()
            values = [float(row[0]) for row in rows]
            if values:
                output[name] = _stats(values)
        return output
    except sqlite3.Error:
        return {}
    finally:
        connection.close()


def run_benchmark(
    *,
    iterations: int = 100,
    history: int = 100,
    paths: Paths | None = None,
) -> dict[str, Any]:
    iterations = max(5, min(5000, int(iterations)))
    history = max(1, min(5000, int(history)))
    resolved = paths or Paths.resolve()
    resolved.ensure()

    frame = _synthetic_frame()
    audio_stats = _time_many(lambda: analyze(frame), iterations, 1000.0)

    report = {
        "jervis_version": __version__,
        "timestamp": time.time(),
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "frozen": bool(getattr(sys, "frozen", False)),
            "audio_backend": backend_name(),
            "native_acceleration": NATIVE_AVAILABLE,
            "pid": os.getpid(),
        },
        "synthetic": {
            "audio_analyze_us": audio_stats,
            **_state_bench(resolved, iterations),
        },
        "live": _live_metrics(resolved.data / "jervis.sqlite3", history),
        "iterations": iterations,
        "history": history,
    }

    history_path = resolved.data / "benchmark-history.jsonl"
    try:
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, separators=(",", ":")) + "\n")
        lines = history_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 50:
            history_path.write_text("\n".join(lines[-50:]) + "\n", encoding="utf-8")
    except OSError:
        pass
    return report


def format_report(report: dict[str, Any]) -> str:
    system = report["system"]
    lines = [
        "Jervis benchmark " + str(report["jervis_version"]),
        "Backend: "
        + str(system["audio_backend"])
        + (" (native)" if system["native_acceleration"] else " (fallback)"),
        "Platform: " + str(system["platform"]),
        "",
        "Synthetic",
    ]

    units = {
        "audio_analyze_us": "µs",
        "kv_roundtrip_ms": "ms",
        "context_snapshot_ms": "ms",
    }
    for name, stats in report["synthetic"].items():
        lines.append(
            "  "
            + name
            + ": median="
            + format(float(stats["median"]), ".3f")
            + units[name]
            + "  p95="
            + format(float(stats["p95"]), ".3f")
            + units[name]
        )

    lines.append("")
    lines.append("Recent live turns")
    if not report["live"]:
        lines.append("  No recorded live latency samples yet.")
    else:
        for name, stats in report["live"].items():
            lines.append(
                "  "
                + name
                + ": median="
                + format(float(stats["median"]), ".1f")
                + "ms  p95="
                + format(float(stats["p95"]), ".1f")
                + "ms  n="
                + str(stats["count"])
            )

    return "\n".join(lines)


def main_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def load_benchmark_history(
    *,
    paths: Paths | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    resolved = paths or Paths.resolve()
    history_path = resolved.data / "benchmark-history.jsonl"
    if not history_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-max(1, int(limit)):]


def format_benchmark_history(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No benchmark history recorded yet."

    lines = ["Jervis benchmark history", ""]
    previous: float | None = None
    for row in rows[-12:]:
        live = row.get("live", {})
        stats = live.get("command_to_reply_ms") if isinstance(live, dict) else None
        median = (
            float(stats["median"])
            if isinstance(stats, dict) and stats.get("median") is not None
            else None
        )
        version = str(row.get("jervis_version", "?"))
        stamp = time.strftime(
            "%Y-%m-%d %H:%M",
            time.localtime(float(row.get("timestamp", 0.0))),
        )
        if median is None:
            lines.append(stamp + "  v" + version + "  no live command latency")
            continue
        delta = ""
        if previous is not None:
            change = median - previous
            direction = "slower" if change > 0 else "faster"
            delta = "  · " + format(abs(change), ".1f") + "ms " + direction
        lines.append(
            stamp
            + "  v"
            + version
            + "  median="
            + format(median, ".1f")
            + "ms"
            + delta
        )
        previous = median
    return "\n".join(lines)
