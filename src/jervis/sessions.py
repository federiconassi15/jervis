from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass(slots=True)
class TrustedSession:
    id: str
    user_id: str
    expires_at: float
    refreshed_at: float
    confidence: float
    source: str


class SessionManager:
    def __init__(self, state, lifetime: int, inactivity: int) -> None:
        self.state = state
        self.lifetime = int(lifetime)
        self.inactivity = int(inactivity)
        self._active: TrustedSession | None = None

    def create(
        self,
        user_id: str,
        confidence: float,
        source: str,
    ) -> TrustedSession:
        now = time.time()
        self._active = TrustedSession(
            secrets.token_urlsafe(18),
            user_id,
            now + self.lifetime,
            now,
            float(confidence),
            source,
        )
        self.state.event("trusted_session_created", user_id)
        return self._active

    def active(self) -> TrustedSession | None:
        session = self._active
        if session is None:
            return None

        now = time.time()
        if (
            now >= session.expires_at
            or now - session.refreshed_at >= self.inactivity
        ):
            self.state.event("trusted_session_expired", session.user_id)
            self._active = None
            return None
        return session

    def refresh(
        self,
        confidence: float | None = None,
    ) -> TrustedSession | None:
        session = self.active()
        if session is None:
            return None

        now = time.time()
        session.refreshed_at = now
        session.expires_at = now + self.lifetime
        if confidence is not None:
            session.confidence = max(session.confidence, float(confidence))
        return session

    def clear(self) -> None:
        self._active = None
