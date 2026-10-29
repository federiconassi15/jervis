"""State-machine foundations for future Jervis Neural Voice 3.0.

Does not capture audio, perform STT, stream to a provider or play TTS. Protects
turn ownership and cancellation across concurrently returning callbacks.
"""
from __future__ import annotations

import enum
import re
import threading
import uuid
from dataclasses import dataclass, field


class Phase(str, enum.Enum):
    IDLE = "idle"
    WAKING = "waking"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass
class Turn:
    id: str
    phase: Phase
    session_id: str | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)


class TurnManager:
    """One active turn. State transitions are guarded by a lock."""

    def __init__(self):
        self._lock = threading.RLock()
        self._turn: Turn | None = None

    def current(self) -> Turn | None:
        with self._lock:
            return self._turn

    def wake(self, *, session_id: str | None = None) -> Turn:
        with self._lock:
            if self._turn is not None:
                raise RuntimeError("A turn is already active")
            turn = Turn(uuid.uuid4().hex, Phase.WAKING, session_id)
            self._turn = turn
            return turn

    def advance(self, turn_id: str, expected: Phase, next_phase: Phase) -> bool:
        permitted = {
            Phase.WAKING: {Phase.LISTENING},
            Phase.LISTENING: {Phase.THINKING},
            Phase.THINKING: {Phase.SPEAKING},
            Phase.SPEAKING: {Phase.LISTENING},
        }
        with self._lock:
            current = self._turn
            if (current is None or current.id != turn_id
                    or current.cancelled.is_set() or current.phase != expected):
                return False
            if next_phase not in permitted.get(expected, set()):
                raise ValueError("Invalid voice phase transition")
            current.phase = next_phase
            return True

    def interrupt(self, *, new_session_id: str | None = None) -> Turn:
        """Cancel active work and start a fresh listening turn.

        Never silently promote a caller-provided identity or authorization;
        session continuity is determined by the existing identity subsystem.
        """
        with self._lock:
            active = self._turn
            if active is None or active.phase not in (Phase.SPEAKING, Phase.THINKING):
                raise RuntimeError("No interruptible response")
            active.cancelled.set()
            # The caller may attach a verified session, otherwise no identity
            # is inherited from a prior user.
            new = Turn(uuid.uuid4().hex, Phase.LISTENING, new_session_id)
            self._turn = new
            return new

    def finish(self, turn_id: str) -> bool:
        with self._lock:
            if self._turn is None or self._turn.id != turn_id:
                return False
            self._turn.cancelled.set()
            self._turn = None
            return True

    def stop(self) -> None:
        with self._lock:
            if self._turn is not None:
                self._turn.cancelled.set()
            self._turn = None


class SpeechChunkBuffer:
    """Incrementally group model text into bounded utterances for future TTS.

    This is display text only. It must not be used as an early authorization or
    execute tool actions based on incomplete model output.
    """

    def __init__(self, *, maximum_chars: int = 4096):
        if not 128 <= maximum_chars <= 65536:
            raise ValueError("Invalid stream buffer capacity")
        self.maximum_chars = maximum_chars
        self._text = ""

    def push(self, chunk: str) -> list[str]:
        if not isinstance(chunk, str):
            raise TypeError("Text chunk expected")
        if len(chunk) + len(self._text) > self.maximum_chars:
            raise ValueError("Streaming response exceeds safe buffer")
        self._text += chunk
        ready = []
        while True:
            match = re.search(r"[.!?](?:\s+|$)", self._text)
            if not match:
                break
            text = self._text[:match.end()].strip()
            if text:
                ready.append(text)
            self._text = self._text[match.end():]
        return ready

    def flush(self) -> str:
        text = self._text.strip()
        self._text = ""
        return text

    def cancel(self) -> None:
        self._text = ""
