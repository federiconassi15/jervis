"""Portable, optional personality preference profiles for Jervis 8.2.

Only changes how allowlisted 8.1 local replies are phrased; it never changes
intent resolution, factual data, permissions, tool decisions or authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .capabilities import Principal
from .local_dialogue import DialogueMemory, LocalReply, compose


@dataclass(frozen=True)
class Persona:
    warmth: float = 0.6
    humor: float = 0.35
    directness: float = 0.55
    expressiveness: float = 0.55
    initiative: float = 0.35
    verbosity: float = 0.5

    def validate(self) -> None:
        for value in asdict(self).values():
            if type(value) not in (float, int) or not math.isfinite(value) or (
                not 0 <= value <= 1
            ):
                raise ValueError("Personality sliders must be finite 0..1 values")

    def local_style(self) -> str:
        self.validate()
        if self.humor >= 0.72 and self.expressiveness >= 0.5:
            return "playful"
        if self.directness >= 0.82 and self.verbosity <= 0.42:
            return "focused"
        return "balanced"


def compose_with_persona(intent, persona: Persona, *,
                         memory: DialogueMemory | None = None) -> LocalReply:
    """Reuse the audited local dialogue templates; never generate tool actions."""
    return compose(intent, style=persona.local_style(), memory=memory)


class PersonaStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        if self.root.is_symlink():
            raise PermissionError("Persona storage cannot be symlinked")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _file(self, principal: Principal) -> Path:
        if not principal.authenticated or not principal.user_id:
            raise PermissionError("Authenticated identity required")
        if principal.device_id is not None:
            raise PermissionError("Remote persona changes not enabled")
        identifier = hashlib.sha256(principal.user_id.encode("utf-8")).hexdigest()[:32]
        return self.root / (identifier + ".json")

    def load(self, principal: Principal) -> Persona:
        path = self._file(principal)
        if not path.exists():
            return Persona()
        if path.is_symlink() or path.stat().st_size > 4096:
            raise PermissionError("Invalid stored personality profile")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != set(Persona.__dataclass_fields__):
            raise ValueError("Invalid personality profile schema")
        persona = Persona(**raw)
        persona.validate()
        return persona

    def save(self, principal: Principal, persona: Persona) -> None:
        persona.validate()
        path = self._file(principal)
        if path.is_symlink():
            raise PermissionError("Refusing to replace symlinked persona")
        payload = json.dumps(asdict(persona), sort_keys=True, separators=(",", ":"))
        temp = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".jervis-persona-", dir=self.root)
            temp = Path(temporary)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if path.is_symlink():
                raise PermissionError("Refusing changed symlink")
            os.replace(temp, path)
            temp = None
            if os.name != "nt":
                path.chmod(0o600)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
