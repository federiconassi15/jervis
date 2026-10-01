from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import Permission
from .permissions import allowed


@dataclass(slots=True)
class Skill:
    name: str
    path: Path
    handler: Callable[[str, dict[str, Any]], object]
    permission: Permission = Permission.KNOWN_USER
    description: str = ""


class SkillManager:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots
        self.skills: dict[str, Skill] = {}

    @staticmethod
    def _permission(value: object) -> Permission:
        if isinstance(value, Permission):
            return value
        try:
            return Permission(str(value))
        except ValueError:
            return Permission.KNOWN_USER

    def discover(self) -> dict[str, Skill]:
        found: dict[str, Skill] = {}
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*/skill.py")):
                name = path.parent.name
                spec = importlib.util.spec_from_file_location("jervis_skill_" + name, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    continue

                handler = getattr(module, "handle", None)
                if not callable(handler):
                    continue
                found[name] = Skill(
                    name=name,
                    path=path,
                    handler=handler,
                    permission=self._permission(
                        getattr(module, "PERMISSION", Permission.KNOWN_USER.value)
                    ),
                    description=str(getattr(module, "DESCRIPTION", "")).strip(),
                )
        self.skills = found
        return found

    def route(
        self,
        text: str,
        context: dict[str, Any],
        *,
        state=None,
        user_id: str | None = None,
        authenticated: bool = False,
    ) -> tuple[str | None, str | None]:
        if not self.skills:
            self.discover()

        for skill in self.skills.values():
            if state is not None and not allowed(
                state,
                user_id,
                skill.permission,
                authenticated,
            ):
                continue
            try:
                result = skill.handler(text, context)
            except Exception as exc:
                if state is not None:
                    state.event("skill_error", skill.name + ": " + str(exc))
                continue
            if result:
                if state is not None:
                    state.event("skill_routed", skill.name)
                return str(result), skill.name
        return None, None
