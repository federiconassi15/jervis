from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import Health


@dataclass(slots=True)
class Check:
    name: str
    probe: Callable[[], Health]
    repair: Callable[[], bool] | None = None
    threshold: int = 3


class Resilience:
    """Runs bounded component checks and repairs only the failing component."""

    def __init__(self, state=None) -> None:
        self.state = state
        self.checks: list[Check] = []
        self.failures: dict[str, int] = {}

    def add(self, check: Check) -> None:
        self.checks.append(check)

    def run_once(self) -> list[Health]:
        results: list[Health] = []
        for check in self.checks:
            try:
                health = check.probe()
            except Exception as exc:
                health = Health(False, check.name, str(exc))
            results.append(health)

            if health.ok:
                self.failures[check.name] = 0
                continue

            count = self.failures.get(check.name, 0) + 1
            self.failures[check.name] = count
            if self.state is not None:
                self.state.event(
                    "health_failure",
                    check.name + " count=" + str(count) + " " + health.detail,
                )

            if count < max(1, int(check.threshold)) or check.repair is None:
                continue
            try:
                repaired = bool(check.repair())
            except Exception as exc:
                repaired = False
                if self.state is not None:
                    self.state.event("repair_error", check.name + ": " + str(exc))
            if repaired:
                self.failures[check.name] = 0
                if self.state is not None:
                    self.state.event("repair_success", check.name)
        return results
