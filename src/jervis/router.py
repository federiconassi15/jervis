from __future__ import annotations

from dataclasses import dataclass
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

    def __init__(self, state, paths, brain: OpenClawBrain) -> None:
        self.state = state
        self.paths = paths
        self.brain = brain
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
            return "I'm using the " + self.agents.selected(user_id, self.brain.agent) + " OpenClaw agent."

        if query.startswith("use agent "):
            requested = text.strip()[10:].strip()
            if self.agents.select(user_id, requested):
                return "I'll use the " + requested + " agent for you."
            return "I couldn't find an OpenClaw agent named " + requested + "."

        if query in {"what do you remember about me", "what do you remember"}:
            memories = self.state.memories(user_id, 8)
            if not memories:
                return "I don't have any explicit memories saved for you yet."
            summary = "; ".join(
                item["key"] + "=" + str(item["value"])
                for item in memories
            )
            return "I remember: " + summary + "."

        return None

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

        self.state.event("brain_route", "openclaw")
        self.brain.agent = self.agents.selected(user_id, self.brain.agent)
        reply = self.brain.ask(text, "jervis:" + user_id)
        return RouteReply(reply.ok, reply.text, "openclaw", reply.error)
