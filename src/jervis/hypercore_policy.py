"""HyperCore 2.0: side-effect-free privacy-aware provider selection policy.

It neither sends prompts nor runs actions. A selected provider must still pass
the host-side capability system and consent rules at the actual call boundary.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .evolve import resolve_offline

_DATA_CLASSES = {"public", "personal", "local_only"}
_COMPLEXITIES = {"fast", "balanced", "deep"}


@dataclass(frozen=True)
class RequestPolicy:
    data_class: str
    complexity: str
    cloud_consent: bool = False
    requires_action: bool = False
    max_cost_units: float = 1.0
    max_latency_ms: float = 60000


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str                       # offline_model, openclaw, cloud
    estimated_latency_ms: float
    estimated_cost_units: float
    supports_deep: bool = False
    enabled: bool = True
    healthy: bool = True


@dataclass(frozen=True)
class RouteDecision:
    route: str
    permitted: bool
    explanation: str


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: float = 30
    _failures: dict[str, int] = field(default_factory=dict)
    _open_until: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not 1 <= self.failure_threshold <= 20:
            raise ValueError("Circuit threshold outside safe range")
        if not 1 <= self.recovery_seconds <= 3600:
            raise ValueError("Circuit recovery window invalid")

    def record(self, name: str, success: bool, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        if success:
            self._failures.pop(name, None)
            self._open_until.pop(name, None)
            return
        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        if count >= self.failure_threshold:
            self._open_until[name] = current + self.recovery_seconds

    def allowed(self, name: str, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        deadline = self._open_until.get(name)
        if deadline is None:
            return True
        if current < deadline:
            return False
        # Half-open: allow one trial, but don't flood concurrent requests.
        # Caller must serialize probes for the same provider.
        return True


class PolicyRouter:
    def __init__(self, breaker: CircuitBreaker | None = None):
        self.breaker = breaker or CircuitBreaker()

    @staticmethod
    def _validate(request: RequestPolicy, providers: tuple[Provider, ...]) -> None:
        if request.data_class not in _DATA_CLASSES:
            raise ValueError("Unknown privacy classification")
        if request.complexity not in _COMPLEXITIES:
            raise ValueError("Unknown complexity classification")
        for value in (request.max_cost_units, request.max_latency_ms):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid resource budget")
        for candidate in providers:
            if candidate.kind not in {"offline_model", "openclaw", "cloud"}:
                raise ValueError("Invalid provider type")
            if not candidate.name or len(candidate.name) > 80:
                raise ValueError("Invalid provider name")
            if not math.isfinite(candidate.estimated_cost_units) or (
                not math.isfinite(candidate.estimated_latency_ms)
            ) or candidate.estimated_cost_units < 0 or candidate.estimated_latency_ms < 0:
                raise ValueError("Invalid provider measurement")

    def choose(self, text: str, request: RequestPolicy,
               providers: tuple[Provider, ...], *,
               now: float | None = None) -> RouteDecision:
        self._validate(request, providers)
        if not isinstance(text, str) or len(text) > 32000:
            raise ValueError("Invalid request size")
        if request.requires_action:
            return RouteDecision(
                "authorization", False,
                "Action execution requires separate capability approval",
            )
        # Existing 8.1 allowlist decides exactly which commands are local.
        if resolve_offline(text) is not None:
            return RouteDecision(
                "offline_fast", True, "Recognized deterministic offline command",
            )
        eligible = []
        for provider in providers:
            if not provider.enabled or not provider.healthy:
                continue
            if not self.breaker.allowed(provider.name, now=now):
                continue
            if request.complexity == "deep" and not provider.supports_deep:
                continue
            if provider.estimated_cost_units > request.max_cost_units:
                continue
            if provider.estimated_latency_ms > request.max_latency_ms:
                continue
            if request.data_class == "local_only" and provider.kind != "offline_model":
                continue
            if request.data_class == "personal" and provider.kind != "offline_model" and (
                not request.cloud_consent
            ):
                continue
            if provider.kind != "offline_model" and not request.cloud_consent:
                continue
            eligible.append(provider)
        if not eligible:
            return RouteDecision(
                "unavailable", False,
                "No healthy provider meets privacy, cost and latency requirements",
            )
        # Prefer lower p95 latency, then lower estimated cost, then stable name.
        selected = min(
            eligible,
            key=lambda p: (p.estimated_latency_ms, p.estimated_cost_units, p.name),
        )
        return RouteDecision(
            selected.name, True, "Selected eligible provider under explicit policy",
        )
