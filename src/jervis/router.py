from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .agents import AgentHub
from .brain import OpenClawBrain
from .skills import SkillManager


@dataclass(slots=True)
class RouteReply:
    ok: bool
    text: str
    route: str
    error: str = ""


class BrainRouter:
    """Routes cheap/local work before handing the request to OpenClaw."""

    def __init__(self, state, paths, brain: OpenClawBrain, config: dict | None = None) -> None:
        self.state = state
        self.paths = paths
        self.brain = brain
        self.config = config or {}
        self.default_agent = brain.agent
        self.agents = AgentHub(state)
        self.skills = SkillManager(
            [
                Path(paths.data) / "skills",
                Path(paths.root) / "skills",
            ]
        )
        self.skills.discover()

    @staticmethod
    def _normalized(text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _local(self, text: str, user_id: str) -> str | None:
        query = self._normalized(text)
        user = self.state.user(user_id)
        name = str(user["name"]) if user else user_id

        if query in {
            "stop",
            "wait",
            "never mind",
            "nevermind",
            "cancel",
            "cancel that",
            "forget it",
        }:
            return "Understood."

        if query in {"who am i", "who am i?", "what is my name", "what's my name"}:
            return "You're " + name + "."

        if query in {"status", "system status", "jervis status", "are you online"}:
            activity = str(self.state.get_kv("activity", "online"))
            return "I'm online. Current state: " + activity + "."

        if query in {"who is here", "who's here", "who is present"}:
            rows = self.state.presence(present_only=True)
            if not rows:
                return "I don't currently have anyone marked as present."
            return "Present: " + ", ".join(str(row["name"]) for row in rows) + "."

        if query in {"which agent are you using", "what agent are you using"}:
            return "I'm using the " + self.agents.selected(user_id, self.default_agent) + " OpenClaw agent."

        if query.startswith("use agent "):
            requested = text.strip()[10:].strip()
            if self.agents.select(user_id, requested):
                return "I'll use the " + requested + " agent for you."
            return "I couldn't find an OpenClaw agent named " + requested + "."

        if query.startswith("remember that "):
            fact = text.strip()[14:].strip()
            if not fact:
                return "Tell me what you want me to remember."
            key = "fact-" + hashlib.sha256(fact.encode("utf-8")).hexdigest()[:12]
            self.state.remember(user_id, key, fact)
            self.state.event("memory_saved", "user=" + user_id + " key=" + key)
            return "Remembered."

        if query in {"clear my memory", "forget everything about me"}:
            self.state.clear_memories(user_id)
            self.state.event("memory_cleared", "user=" + user_id)
            return "Your explicit Jervis memory is cleared."

        if query in {"what do you remember about me", "what do you remember"}:
            memories = self.state.memories(user_id, 8)
            if not memories:
                return "I don't have any explicit memories saved for you yet."
            return "I remember: " + "; ".join(str(item["value"]) for item in memories) + "."

        return None

    def _tier(self, text: str) -> tuple[str, str]:
        brain = self.config.get("brain", {})
        lowered = text.lower()
        deep_markers = (
            "analyze",
            "analyse",
            "research",
            "compare",
            "debug",
            "design",
            "architecture",
            "step by step",
            "reason",
        )
        if len(text) > 500 or any(marker in lowered for marker in deep_markers):
            return "deep", str(brain.get("deep_thinking", "high"))
        if len(text) < 180:
            return "fast", str(brain.get("fast_thinking", "low"))
        return "default", str(
            brain.get("default_thinking", brain.get("thinking", "low"))
        )

    def _context_prompt(
        self,
        text: str,
        snapshot: dict[str, Any],
    ) -> str:
        user = snapshot.get("user")
        parts = ["You are Jervis, a concise voice assistant."]
        if user is not None:
            parts.append("Current user: " + str(user["name"]) + ".")
            if user["honorific"]:
                label = "ma'am" if str(user["honorific"]) == "maam" else "sir"
                parts.append("Preferred form of address: " + label + ".")

        memories = snapshot.get("memories") or []
        if memories:
            limit = max(
                200,
                int(self.config.get("brain", {}).get("memory_context_chars", 1600)),
            )
            memory_text = "\n".join(
                "- " + str(item["value"]) for item in reversed(memories)
            )
            parts.append("Explicit local memories:\n" + memory_text[:limit])

        dialogue = snapshot.get("dialogue") or []
        if dialogue and self.config.get("brain", {}).get("inject_recent_dialogue", False):
            parts.append(
                "Recent local conversation context:\n"
                + "\n".join(
                    str(row["role"]) + ": " + str(row["text"])
                    for row in dialogue
                )
            )

        parts.append("Current user request:\n" + text)
        return "\n\n".join(parts)

    def ask(
        self,
        text: str,
        user_id: str,
        *,
        authenticated: bool = True,
        context: dict[str, Any] | None = None,
    ) -> RouteReply:
        local = self._local(text, user_id)
        if local is not None:
            self.state.event("brain_route", "local")
            return RouteReply(True, local, "local")

        skill_reply, skill_name = self.skills.route(
            text,
            context or {"user_id": user_id},
            state=self.state,
            user_id=user_id,
            authenticated=authenticated,
        )
        if skill_reply is not None:
            self.state.event("brain_route", "skill:" + str(skill_name))
            return RouteReply(True, skill_reply, "skill:" + str(skill_name))

        tier, thinking = self._tier(text)
        route_name = "openclaw:" + tier
        brain_config = self.config.get("brain", {})
        snapshot = self.state.context_snapshot(
            user_id,
            memory_limit=int(brain_config.get("memory_context_items", 6)),
            dialogue_limit=8 if brain_config.get("inject_recent_dialogue", False) else 0,
        )
        self.brain.agent = str(snapshot.get("agent") or self.default_agent)
        self.state.event("brain_route", route_name)
        reply = self.brain.ask(
            self._context_prompt(text, snapshot),
            "jervis:" + user_id,
            thinking=thinking,
        )
        self.state.event(
            "brain_transport",
            str(getattr(self.brain, "last_transport", "unknown")),
        )
        return RouteReply(reply.ok, reply.text, route_name, reply.error)
