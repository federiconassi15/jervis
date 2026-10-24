"""Fast, fully offline, non-generative response composer for Jervis 8.1.

The intent resolver alone decides what may be recognized. This module chooses
auditable wording without executing anything, networking, or storing user text.
"""
from __future__ import annotations

import json
import math
import os
import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol


class OfflineCommand(Protocol):
    name: str
    response: str
    requires_confirmation: bool


@dataclass(frozen=True)
class Frame:
    key: str
    tone: str
    heads: tuple[str, ...]
    cores: tuple[str, ...]
    tails: tuple[str, ...] = ("",)
    weight: float = 1.0
    repeat_only: bool = False
    daypart: str = ""


# Compatible sentence fragments, rather than randomly mixed unrelated phrases.
_FRAMES: dict[str, tuple[Frame, ...]] = {
    "greeting": (
        Frame("greet-warm", "warm", ("Hey!", "Hello!", "Good to see you.", "Jervis here."),
              ("What are we working on?", "What's the plan?", "Ready when you are.",
               "What can I help with?"), ("", "I'm listening.", "Your call.")),
        Frame("greet-playful", "playful", ("Oh, hey.", "Well, hello!", "Look who's here."),
              ("Got something interesting in mind?", "What are we building today?",
               "What are we getting into?"), ("", "I'm curious.", "Let's hear it.")),
        Frame("greet-focused", "focused", ("Hello.", "Ready.", "I'm here."),
              ("What do you need?", "What should we tackle?", "How can I help?")),
        Frame("greet-again", "warm", ("Still here!", "Hello again.", "Back for round two?"),
              ("What's next?", "Anything specific in mind?", "Ready for the next one."),
              repeat_only=True),
        Frame("greet-morning", "warm", ("Morning!", "Good morning."),
              ("What are we tackling first?", "Ready when you are."), daypart="morning"),
        Frame("greet-evening", "warm", ("Evening!", "Good evening."),
              ("What's on the agenda?", "How can I help?"), daypart="evening"),
    ),
    "help": (
        Frame("help-warm", "warm", ("Of course.", "Here's the shortlist.", "Sure thing."),
              ("Try 'time', 'status', or 'diagnostics'.",
               "I can handle 'time', 'status', and 'diagnostics' offline."),
              ("", "You can say hello, too.", "No network needed for those.")),
        Frame("help-focused", "focused", ("Offline commands:", "Available locally:"),
              ("'time', 'status', 'diagnostics', and 'help'.",
               "'help', 'time', 'status', or 'diagnostics'.")),
        Frame("help-repeat", "warm", ("Another quick rundown?", "Still exploring?"),
              ("Use 'time', 'status', or 'diagnostics' locally.",
               "Try 'help', 'time', 'status', or 'diagnostics'."), repeat_only=True),
        Frame("help-playful", "playful", ("A little tour?", "Easy starting point."),
              ("Ask for 'time', 'status', or 'diagnostics'.",
               "Try 'help', 'time', 'status', or 'diagnostics'."),
              ("", "No cloud involved.", "Small commands, quick answers.")),
    ),
    "time": (
        Frame("time-warm", "warm", ("Right now,", "On this machine,", "Local clock says:"),
              ("it's {time}.", "{time}.")),
        Frame("time-focused", "focused", ("Local time:", "Clock:"), ("{time}.",)),
        Frame("time-repeat", "warm", ("Another clock check?", "Still keeping time?"),
              ("It's {time} locally.", "The local time is {time}."), repeat_only=True),
        Frame("time-playful", "playful", ("Checking the clock...", "Time check!"),
              ("It's {time} here.", "The local clock reads {time}.")),
    ),
    "status": (
        Frame("status-warm", "warm", ("Let's get the real picture.", "Sure.", "Want a health overview?"),
              ("Run 'jervis status' for the actual system state.",
               "'jervis status' will show the current system state."),
              ("", "Better to check than guess.")),
        Frame("status-focused", "focused", ("System status:", "For system health:"),
              ("run 'jervis status'.", "use 'jervis status' for live details.")),
        Frame("status-repeat", "warm", ("Checking again?", "Another status check?"),
              ("Run 'jervis status' for current details.",
               "Use 'jervis status' to verify the machine state."), repeat_only=True),
        Frame("status-playful", "playful", ("Let's look under the hood.", "Time for a systems check."),
              ("Run 'jervis status' to see what's actually happening.",
               "Use 'jervis status' for the real numbers.")),
    ),
    "diagnostics": (
        Frame("doctor-warm", "warm", ("Let's investigate.", "I can point you to the checks.",
                                   "Need a closer look?"),
              ("Run 'jervis doctor' for local diagnostics.",
               "'jervis doctor' checks the local setup."),
              ("", "It'll report what it can verify.")),
        Frame("doctor-focused", "focused", ("Diagnostics:", "For local checks:"),
              ("run 'jervis doctor'.", "use 'jervis doctor'.")),
        Frame("doctor-repeat", "warm", ("Digging deeper?", "Another diagnostics pass?"),
              ("Run 'jervis doctor' for current checks.",
               "Use 'jervis doctor' to verify local health."), repeat_only=True),
        Frame("doctor-playful", "playful", ("Detective mode, then.", "Let's find the culprit."),
              ("Run 'jervis doctor' for a proper inspection.",
               "'jervis doctor' is the next step.")),
    ),
}

_MAX_RECENT = 24
_MAX_FRAMES = 64
_MAX_FILE_BYTES = 16384
_STYLES = frozenset({"balanced", "playful", "focused"})


@dataclass
class DialogueMemory:
    """Anonymous choice identifiers only; never the input or generated words."""

    recent: list[str] = field(default_factory=list)
    frames: dict[str, int] = field(default_factory=dict)
    last_intent: str = ""
    streak: int = 0

    @classmethod
    def from_data(cls, data: object) -> "DialogueMemory":
        if not isinstance(data, dict) or data.get("version") != 1:
            return cls()
        recent = data.get("recent", [])
        counts = data.get("frames", {})
        last_intent = data.get("last_intent", "")
        streak = data.get("streak", 0)
        if not isinstance(recent, list) or not isinstance(counts, dict):
            return cls()
        if not isinstance(last_intent, str) or last_intent not in {*_FRAMES, ""}:
            last_intent = ""
        if not isinstance(streak, int) or isinstance(streak, bool):
            streak = 0
        clean_recent = [value for value in recent[-_MAX_RECENT:]
                        if isinstance(value, str) and 0 < len(value) <= 80]
        clean_counts = {key: min(value, 10000) for key, value in list(counts.items())[:_MAX_FRAMES]
                        if isinstance(key, str) and len(key) <= 32
                        and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
        return cls(clean_recent, clean_counts, last_intent, max(0, min(streak, 30)))

    def to_data(self) -> dict:
        return {"version": 1, "recent": self.recent[-_MAX_RECENT:],
                "frames": self.frames, "last_intent": self.last_intent,
                "streak": self.streak}


@dataclass(frozen=True)
class LocalReply:
    intent: str
    text: str
    tone: str
    variant: str
    requires_confirmation: bool = False


def _daypart(now: datetime) -> str:
    if 5 <= now.hour < 12:
        return "morning"
    if 17 <= now.hour < 24:
        return "evening"
    return ""


def _tone_multiplier(tone: str, style: str, streak: int) -> float:
    if style == "focused":
        return {"focused": 5.0, "warm": 0.0, "playful": 0.0}[tone]
    if style == "playful":
        return {"focused": 0.25, "warm": 1.15, "playful": 3.0}[tone]
    return {"focused": 0.85, "warm": 2.0, "playful": 0.8 + min(streak, 3) * 0.15}[tone]


def compose(
    intent: OfflineCommand, *, memory: DialogueMemory | None = None,
    style: str = "balanced", rng: random.Random | None = None,
    now: datetime | None = None,
) -> LocalReply:
    """Score coherent candidates for tone, fatigue, novelty and repeat context.

    Never repeats a complete template in its 24-turn cooldown while unused
    alternatives exist. Only whitelisted intents have generative templates.
    """
    if style not in _STYLES:
        raise ValueError("Unsupported local response style")
    if memory is None:
        memory = DialogueMemory()
    if rng is None:
        rng = secrets.SystemRandom()
    if now is None:
        now = datetime.now().astimezone()
    if intent.name not in _FRAMES:
        return LocalReply(intent.name, intent.response, "focused", "canonical",
                          intent.requires_confirmation)

    repeated = memory.last_intent == intent.name
    streak = memory.streak + 1 if repeated else 1
    context = {"time": now.strftime("%H:%M")}
    parts_recent = set()
    for variant in memory.recent[-9:]:
        parts = variant.split("/")
        if len(parts) == 4:
            parts_recent.update((f"{parts[0]}:h:{parts[1]}",
                                 f"{parts[0]}:b:{parts[2]}",
                                 f"{parts[0]}:t:{parts[3]}"))

    candidates: list[tuple[float, str, str, str]] = []
    for frame in _FRAMES[intent.name]:
        if frame.repeat_only and streak < 2:
            continue
        if frame.daypart and frame.daypart != _daypart(now):
            continue
        tone_fit = _tone_multiplier(frame.tone, style, streak)
        if not tone_fit:
            continue
        age_penalty = 1.0 / (1.0 + math.sqrt(memory.frames.get(frame.key, 0)) * 0.17)
        for h, head in enumerate(frame.heads):
            for b, core in enumerate(frame.cores):
                for t, tail in enumerate(frame.tails):
                    variant = f"{frame.key}/{h}/{b}/{t}"
                    if variant in memory.recent[-_MAX_RECENT:]:
                        continue
                    penalty = 1.0
                    for marker in (f"{frame.key}:h:{h}", f"{frame.key}:b:{b}",
                                   f"{frame.key}:t:{t}"):
                        if marker in parts_recent:
                            penalty *= 0.78
                    score = frame.weight * tone_fit * age_penalty * penalty
                    if score > 0:
                        sentence = " ".join(p for p in (head, core, tail) if p)
                        candidates.append((score, variant, sentence.format_map(context), frame.tone))
    if not candidates:
        # Cooldown exhausted: reset only the recent set; retain fatigue history.
        memory.recent.clear()
        return compose(intent, memory=memory, style=style, rng=rng, now=now)

    threshold = rng.random() * sum(candidate[0] for candidate in candidates)
    chosen = candidates[-1]
    for candidate in candidates:
        threshold -= candidate[0]
        if threshold < 0:
            chosen = candidate
            break
    _, variant, text, tone = chosen
    frame_key = variant.split("/", 1)[0]
    memory.recent.append(variant)
    del memory.recent[:-_MAX_RECENT]
    memory.frames[frame_key] = min(10000, memory.frames.get(frame_key, 0) + 1)
    memory.last_intent = intent.name
    memory.streak = min(streak, 30)
    return LocalReply(intent.name, text, tone, variant, intent.requires_confirmation)


class DialogueStore:
    """Best-effort private cache; no raw user utterances or response text."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> DialogueMemory:
        try:
            if self.path.is_symlink() or self.path.parent.is_symlink():
                return DialogueMemory()
            if not self.path.is_file() or self.path.stat().st_size > _MAX_FILE_BYTES:
                return DialogueMemory()
            return DialogueMemory.from_data(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, ValueError, TypeError):
            return DialogueMemory()

    def save(self, memory: DialogueMemory) -> None:
        """Atomic best-effort update; a cache error never blocks the command."""
        path = self.path
        tmp: Path | None = None
        try:
            if path.is_symlink() or path.parent.is_symlink():
                return
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            payload = json.dumps(memory.to_data(), separators=(",", ":"))
            if len(payload) > _MAX_FILE_BYTES:
                return
            tmp = path.parent / (".dialogue-" + secrets.token_hex(12) + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
            if path.is_symlink():
                return
            os.replace(tmp, path)
        except OSError:
            return
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass


def reply_offline(intent: OfflineCommand, *, cache: Path | None = None,
                  style: str = "balanced", rng: random.Random | None = None,
                  now: datetime | None = None) -> LocalReply:
    """CLI entry point; no cache means an ephemeral, memory-free response."""
    store = DialogueStore(cache) if cache is not None else None
    memory = store.load() if store else DialogueMemory()
    reply = compose(intent, memory=memory, style=style, rng=rng, now=now)
    if store:
        store.save(memory)
    return reply
