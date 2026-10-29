# Jervis 8.2 — Automation Builder durable scheduler foundation

**Experimental, not released.** Implements bounded owner-scoped interval, daily
timezone-aware, and trusted event-trigger rules. It stores pending work with
idempotent event IDs in SQLite; it does **not** execute scripts, model output,
plugins, network calls or remote commands.

Rules default disabled. The owner must explicitly enable them. Time-triggered
rules skip missed interval backlogs after prolonged downtime. Local daily
scheduling uses IANA time zones. Spring-forward nonexistent times skip that day;
fall-back ambiguous times choose the first occurrence.

This module requires a future audited linkage to Mission Control (including
fresh per-action capability checks and approval), plus GUI editing, persistence
migration, secure backup inclusion and service-level integration. A pending
record is not evidence that an action ran. Executed actions must be confirmed
by a trusted executor. No remote automation may bypass host policy.
