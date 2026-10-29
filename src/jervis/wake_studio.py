"""Local wake-word profile storage for Jervis 8.2 Studio (experimental)."""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class WakeProfile:
    name: str
    phrase: str
    threshold: float = 1e-20
    sample_rate: int = 16000


def _validate(profile: WakeProfile) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", profile.name):
        raise ValueError("Invalid wake profile name")
    if not re.fullmatch(r"[a-z0-9]+(?:[ -][a-z0-9]+){0,5}", profile.phrase):
        raise ValueError("Wake phrase must be 1-6 simple words")
    if not 1e-50 <= profile.threshold <= 1e-1:
        raise ValueError("Wake keyword threshold outside safe range")
    if profile.sample_rate not in {8000, 16000}:
        raise ValueError("Unsupported PocketSphinx sample rate")


class WakeStudio:
    def __init__(self, file: Path):
        self.file = Path(file)
        if self.file.is_symlink():
            raise PermissionError("Wake profiles cannot be a symlink")
        self.file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    def load(self) -> dict[str, WakeProfile]:
        if not self.file.exists():
            return {"default": WakeProfile("default", "jervis")}
        if self.file.is_symlink():
            raise PermissionError("Wake profile target was replaced by symlink")
        if self.file.stat().st_size > 16384:
            raise ValueError("Wake profile file too large")
        raw = json.loads(self.file.read_text("utf-8"))
        if not isinstance(raw, dict) or len(raw) > 16:
            raise ValueError("Invalid wake profile collection")
        profiles = {}
        for name, item in raw.items():
            if not isinstance(item, dict):
                raise ValueError("Malformed wake profile")
            profile = WakeProfile(
                name=name,
                phrase=item["phrase"],
                threshold=float(item["threshold"]),
                sample_rate=int(item["sample_rate"]),
            )
            _validate(profile)
            profiles[name] = profile
        if "default" not in profiles:
            raise ValueError("Missing fallback wake profile")
        return profiles

    def save(self, profiles: dict[str, WakeProfile]) -> None:
        if "default" not in profiles or len(profiles) > 16:
            raise ValueError("Default profile required; max 16 profiles")
        for name, item in profiles.items():
            if item.name != name:
                raise ValueError("Inconsistent profile identifier")
            _validate(item)
        if self.file.exists() or self.file.is_symlink():
            self.load()  # Refuse to overwrite invalid or replaced configuration.
        payload = json.dumps(
            {name: {k: v for k, v in asdict(profile).items() if k != "name"}
             for name, profile in sorted(profiles.items())},
            separators=(",", ":"),
        )
        temporary = None
        try:
            fd, name = tempfile.mkstemp(prefix=".jervis-wake-", dir=self.file.parent)
            temporary = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if self.file.is_symlink():
                raise PermissionError("Refusing to overwrite a symlinked wake profile")
            os.replace(temporary, self.file)
            temporary = None
            if os.name != "nt":
                self.file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
