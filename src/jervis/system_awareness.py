"""Explicit, read-only system resource snapshot for Jervis 8.2.

No process names, windows, command lines, environment, files, serials, IPs,
screenshot content, or user identifiers are collected. No background polling.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class ResourceSnapshot:
    sampled_at: float
    cpu_percent: float
    memory_percent: float
    memory_available_mib: int
    disk_percent: float
    disk_free_mib: int
    battery_percent: float | None
    on_ac_power: bool | None


def _pct(value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite system metric")
    return round(max(0.0, min(100.0, result)), 1)


def sample_system(*, consent: bool = False, disk_root: Path | None = None,
                  clock=time.time) -> ResourceSnapshot:
    """Only sample after user-driven consent. Never acquire private context."""
    if not consent:
        raise PermissionError("Explicit resource monitoring consent required")
    root = Path(disk_root) if disk_root is not None else Path.home().anchor
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(str(root))
    battery = psutil.sensors_battery()
    return ResourceSnapshot(
        sampled_at=float(clock()),
        cpu_percent=_pct(psutil.cpu_percent(interval=None)),
        memory_percent=_pct(ram.percent),
        memory_available_mib=max(0, int(ram.available // (1024 * 1024))),
        disk_percent=_pct(disk.percent),
        disk_free_mib=max(0, int(disk.free // (1024 * 1024))),
        battery_percent=None if battery is None else _pct(battery.percent),
        on_ac_power=None if battery is None else bool(battery.power_plugged),
    )
