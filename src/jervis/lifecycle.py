from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import Paths


@dataclass(slots=True)
class CrashState:
    previous_unclean: bool
    consecutive_crashes: int


def marker_path(paths: Paths | None = None) -> Path:
    resolved = paths or Paths.resolve()
    resolved.cache.mkdir(parents=True, exist_ok=True)
    return resolved.cache / "runtime-session.json"


def inspect_runtime(paths: Paths | None = None) -> CrashState:
    resolved = paths or Paths.resolve()
    marker = marker_path(resolved)
    previous_unclean = False
    crashes = 0
    if marker.exists():
        try:
            previous = json.loads(marker.read_text(encoding="utf-8"))
            previous_unclean = not bool(previous.get("clean", False))
            crashes = int(previous.get("consecutive_crashes", 0))
        except Exception:
            previous_unclean = True
        if previous_unclean:
            crashes += 1
        else:
            crashes = 0
    return CrashState(previous_unclean, crashes)


def begin_runtime(paths: Paths | None = None) -> CrashState:
    resolved = paths or Paths.resolve()
    marker = marker_path(resolved)
    state = inspect_runtime(resolved)
    crashes = state.consecutive_crashes

    marker.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "started_at": time.time(),
                "clean": False,
                "consecutive_crashes": crashes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return state


def end_runtime(paths: Paths | None = None) -> None:
    marker = marker_path(paths)
    try:
        data = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
    except Exception:
        data = {}
    data["clean"] = True
    data["ended_at"] = time.time()
    data["consecutive_crashes"] = 0
    marker.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
