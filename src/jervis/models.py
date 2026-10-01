from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Permission(str, Enum):
    PUBLIC = "public"
    KNOWN_USER = "known_user"
    TRUSTED_USER = "trusted_user"
    OWNER = "owner"
    AUTH_REQUIRED = "auth_required"


class ConfidenceBand(str, Enum):
    STRONG = "strong"
    SESSION_ASSISTED = "session_assisted"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class SpeakerMatch:
    user_id: str | None
    score: float
    margin: float
    band: ConfidenceBand
    source: str


@dataclass(slots=True)
class AudioDevice:
    index: int
    name: str
    inputs: int
    outputs: int
    default_samplerate: float
    hostapi: str = ""


@dataclass(slots=True)
class Health:
    ok: bool
    component: str
    detail: str = ""
