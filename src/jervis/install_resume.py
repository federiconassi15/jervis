from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import Paths


@dataclass(slots=True)
class InstallResumeState:
    active: bool
    step: int
    title: str
    updated_at: float


def journal_path(paths: Paths | None = None) -> Path:
    resolved = paths or Paths.resolve()
    resolved.cache.mkdir(parents=True, exist_ok=True)
    return resolved.cache / "install-resume.json"


def read_resume(paths: Paths | None = None) -> InstallResumeState | None:
    path = journal_path(paths)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return InstallResumeState(
            active=bool(data.get("active", True)),
            step=int(data.get("step", 0)),
            title=str(data.get("title", "")),
            updated_at=float(data.get("updated_at", 0.0)),
        )
    except Exception:
        return None


def write_resume(step: int, title: str, *, paths: Paths | None = None) -> None:
    path = journal_path(paths)
    path.write_text(
        json.dumps(
            {
                "active": True,
                "step": int(step),
                "title": str(title),
                "updated_at": time.time(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def clear_resume(paths: Paths | None = None) -> None:
    journal_path(paths).unlink(missing_ok=True)
