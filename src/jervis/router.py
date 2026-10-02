from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import time
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

    @staticmethod
    def _duration_seconds(text: str) -> tuple[int, re.Match[str] | None]:
        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*"
            r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return 0, None
        amount = float(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith(("second", "sec")):
            scale = 1
        elif unit.startswith(("minute", "min")):
            scale = 60
        elif unit.startswith(("hour", "hr")):
            scale = 3600
        else:
            scale = 86400
        return max(1, int(amount * scale)), match

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
            running = next(
                (
                    row
                    for row in self.state.recent_agent_runs(user_id, 8)
                    if str(row["status"]) == "running"
                ),
                None,
            )
            if running is not None and self.state.request_agent_cancel(int(running["id"])):
                return "Cancelling the active agent task."
            return "Understood."

        if query in {"who am i", "who am i?", "what is my name", "what's my name"}:
            return "You're " + name + "."

        if query in {"status", "system status", "jervis status", "are you online"}:
            activity = str(self.state.get_kv("activity", "online"))
            return "I'm online. Current state: " + activity + "."

        if query in {
            "tell me when openclaw is back",
            "tell me when openclaw is online",
            "tell me when openclaw is available",
            "let me know when openclaw is back",
            "let me know when openclaw is online",
            "let me know when openclaw is available",
        }:
            key = "watch-openclaw-" + user_id
            watch_id = self.state.create_condition_watch(
                key,
                "openclaw_ready",
                {},
                "OpenClaw is healthy again.",
                user_id,
                reason="You asked me to tell you when OpenClaw was available again.",
                priority=15,
                expires_at=time.time() + 7 * 86400,
                check_interval=60,
            )
            self.state.event(
                "condition_watch_created",
                "id=" + str(watch_id) + " kind=openclaw_ready user=" + user_id,
            )
            return "Okay. I'll tell you when OpenClaw is healthy again."

        lowered = text.strip().lower()
        if lowered.startswith("tell me when file ") and lowered.endswith(" exists"):
            path_text = text.strip()[18:-7].strip()
            if not path_text:
                return "Tell me which file path to watch."
            key = "watch-file-" + hashlib.sha256(
                (user_id + path_text).encode("utf-8")
            ).hexdigest()[:12]
            watch_id = self.state.create_condition_watch(
                key,
                "file_exists",
                {"path": path_text},
                "The file now exists: " + path_text,
                user_id,
                reason="You asked me to tell you when this file appeared.",
                priority=10,
                expires_at=time.time() + 7 * 86400,
                check_interval=15,
            )
            self.state.event(
                "condition_watch_created",
                "id=" + str(watch_id) + " kind=file_exists user=" + user_id,
            )
            return "Okay. I'll watch for that file."

        if query in {
            "what are you watching for me",
            "what condition watches do i have",
            "show my watches",
        }:
            rows = self.state.condition_watches(user_id, active_only=True, limit=8)
            if not rows:
                return "You don't have any active condition watches."
            return "Active watches: " + "; ".join(
                "#" + str(row["id"]) + " " + str(row["kind"])
                for row in rows
            ) + "."

        if query.startswith("remind me in "):
            seconds, match = self._duration_seconds(text)
            if not seconds or match is None:
                return "Tell me how long from now, for example: remind me in 20 minutes."
            remainder = text[match.end():].strip()
            if remainder.lower().startswith("to "):
                remainder = remainder[3:].strip()
            if not remainder:
                return "What should I remind you about?"
            due = time.time() + seconds
            proactive = self.config.get("proactive", {})
            grace = max(
                3600,
                int(proactive.get("default_ttl_seconds", 86400)),
            )
            key = "reminder-" + hashlib.sha256(
                (user_id + str(due) + remainder).encode("utf-8")
            ).hexdigest()[:12]
            self.state.notify(
                key,
                "Reminder: " + remainder,
                user_id,
                priority=10,
                expires_at=due + grace,
                not_before=due,
                reason="You asked me to remind you.",
            )
            self.state.event(
                "reminder_created",
                "user=" + user_id + " due_in=" + str(seconds),
            )
            if seconds < 60:
                when = str(seconds) + " seconds"
            elif seconds < 3600:
                when = str(round(seconds / 60)) + " minutes"
            elif seconds < 86400:
                when = str(round(seconds / 3600, 1)).rstrip("0").rstrip(".") + " hours"
            else:
                when = str(round(seconds / 86400, 1)).rstrip("0").rstrip(".") + " days"
            return "Okay. I'll remind you in " + when + "."

        if query.startswith(("don't interrupt me for ", "dont interrupt me for ")):
            seconds, _match = self._duration_seconds(text)
            if not seconds:
                return "Tell me how long you want quiet time for."
            until = time.time() + seconds
            self.state.set_kv(
                "proactive.busy_until." + user_id,
                until,
            )
            self.state.event(
                "proactive_busy",
                "user=" + user_id + " seconds=" + str(seconds),
            )
            return "Understood. I won't proactively interrupt you until then."

        if query in {
            "why did you tell me that",
            "why did you say that",
            "why did you remind me",
            "why that notification",
        }:
            delivery = self.state.get_kv(
                "proactive.last_delivery." + user_id
            )
            if not isinstance(delivery, dict):
                return "I don't have a recent proactive message to explain."
            reason = str(delivery.get("reason") or "").strip()
            if reason:
                return reason
            return "That was the next eligible proactive item in your queue."

        if query in {
            "what reminders do i have",
            "show my reminders",
            "what are my reminders",
        }:
            rows = self.state.pending_notifications(user_id, 8)
            reminders = [
                str(row["text"])
                for row in rows
                if str(row["key"]).startswith("reminder-")
            ]
            if not reminders:
                return "You don't have any pending reminders."
            return "Pending reminders: " + "; ".join(reminders)

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
            self.state.remember(
                user_id,
                key,
                fact,
                provenance="voice:explicit",
                importance=0.85,
            )
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

        summaries = snapshot.get("summaries") or []
        if summaries:
            parts.append(
                "Recent session continuity:\n"
                + "\n".join(
                    "- "
                    + (
                        (str(item.get("topic")) + ": ")
                        if item.get("topic")
                        else ""
                    )
                    + str(item.get("summary", ""))
                    for item in summaries
                )
            )

        dialogue = snapshot.get("dialogue") or []
        if dialogue:
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

        if self.config.get("_safe_mode", False):
            self.state.event("brain_route", "safe-mode")
            return RouteReply(
                False,
                "Safe mode is active. External skills and OpenClaw actions are disabled.",
                "safe-mode",
                "safe mode blocks non-local routing",
            )

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
        continuity = self.config.get("continuity", {})
        normalized = self._normalized(text)
        correction = normalized.startswith(
            (
                "no i meant",
                "no, i meant",
                "actually i meant",
                "actually, i meant",
                "i meant",
                "correction",
            )
        )
        dialogue_limit = (
            int(continuity.get("correction_context_turns", 6))
            if correction
            else (
                8
                if brain_config.get("inject_recent_dialogue", False)
                else 0
            )
        )
        if correction:
            self.state.event("continuity_correction", "user=" + user_id)

        snapshot = self.state.context_snapshot(
            user_id,
            memory_limit=int(brain_config.get("memory_context_items", 6)),
            dialogue_limit=dialogue_limit,
            summary_limit=int(
                continuity.get("session_summary_items", 3)
            ),
            query=text,
        )
        self.brain.agent = str(snapshot.get("agent") or self.default_agent)
        self.state.event("brain_route", route_name)
        run_id = self.state.begin_agent_run(
            user_id,
            self.brain.agent,
            route_name,
        )
        try:
            reply = self.brain.ask(
                self._context_prompt(text, snapshot),
                "jervis:" + user_id,
                thinking=thinking,
                cancel_check=(
                    (lambda: self.state.agent_cancel_requested(run_id))
                    if tier == "deep"
                    else None
                ),
            )
        except Exception as exc:
            self.state.finish_agent_run(
                run_id,
                "failed",
                type(exc).__name__ + ": " + str(exc),
            )
            raise

        for action in getattr(reply, "actions", []) or []:
            self.state.add_agent_action(
                run_id,
                str(action.get("kind") or "tool"),
                str(action.get("name") or "unknown"),
                status=str(action.get("status") or ""),
                detail=str(action.get("detail") or ""),
            )

        self.state.finish_agent_run(
            run_id,
            (
                "cancelled"
                if getattr(reply, "cancelled", False)
                else ("completed" if reply.ok else "failed")
            ),
            reply.error,
        )
        self.state.event(
            "brain_transport",
            str(getattr(self.brain, "last_transport", "unknown")),
        )
        return RouteReply(reply.ok, reply.text, route_name, reply.error)
