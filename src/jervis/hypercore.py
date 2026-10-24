"""HyperCore 8.1 lightweight timing and capacity-aware fast routing.

The local route avoids any external model or subprocess. Metrics use monotonic
clocks, bounded histograms, and report both median and tail latency. The
performance target must be measured against 8.0 on the same machine.
"""
from __future__ import annotations

import math
import random
import statistics
import time
from collections import deque
from datetime import datetime
from typing import Callable

from .evolve import resolve_offline
from .local_dialogue import DialogueMemory, compose


class LatencyWindow:
    """Bounded in-memory latency rolling window; no transcript retention."""

    def __init__(self, limit: int = 256):
        if not 4 <= limit <= 4096:
            raise ValueError("Latency window size must be 4..4096")
        self._values: deque[float] = deque(maxlen=limit)

    def record(self, duration_ms: float) -> None:
        if not math.isfinite(duration_ms) or duration_ms < 0:
            raise ValueError("Invalid elapsed duration")
        self._values.append(duration_ms)

    def snapshot(self) -> dict[str, float | int]:
        ordered = sorted(self._values)
        if not ordered:
            return {"count": 0}
        p95_index = math.ceil((len(ordered) - 1) * 0.95)
        return {"count": len(ordered), "median_ms": statistics.median(ordered),
                "p95_ms": ordered[p95_index], "max_ms": ordered[-1]}


class FastRouter:
    """Keeps coherent local responses in process, never caches user input."""

    def __init__(self, style: str = "balanced"):
        if style not in {"balanced", "focused", "playful"}:
            raise ValueError("Unsupported local style")
        self.style = style
        self.memory = DialogueMemory()
        self.latency = LatencyWindow()

    def respond(self, command: str) -> str | None:
        started = time.perf_counter_ns()
        try:
            intent = resolve_offline(command)
            if intent is None:
                return None
            return compose(intent, memory=self.memory, style=self.style).text
        finally:
            self.latency.record((time.perf_counter_ns() - started) / 1_000_000)


def benchmark_fast_path(*, iterations: int = 250,
                        clock_ns: Callable[[], int] = time.perf_counter_ns) -> dict:
    """Benchmark only local routing and adaptive response composition."""
    if not isinstance(iterations, int) or not 25 <= iterations <= 5000:
        raise ValueError("iterations must be 25..5000")
    responses = []
    costs = []
    memory = DialogueMemory()
    rng = random.Random(1930)
    now = datetime.now().astimezone()
    phrases = ("hello", "help", "time", "status", "diagnostics")
    for index in range(iterations):
        phrase = phrases[index % len(phrases)]
        started = clock_ns()
        intent = resolve_offline(phrase)
        if intent is None:
            raise RuntimeError("Missing fast route: " + phrase)
        response = compose(intent, memory=memory, rng=rng, now=now)
        ended = clock_ns()
        if index < 10:
            responses.append(response.variant)
        costs.append(max(0.0, (ended - started) / 1_000_000))
    ordered = sorted(costs)
    return {"iterations": iterations,
            "median_ms": statistics.median(ordered),
            "p95_ms": ordered[math.ceil((len(ordered) - 1) * 0.95)],
            "max_ms": ordered[-1],
            "sample_variants": responses,
            "scope": "offline intent resolution and response composition only"}
