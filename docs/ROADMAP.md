# Jervis Roadmap

This roadmap describes direction, not guaranteed release dates. Release notes are derived from actual code changes; the roadmap is for intent and sequencing.

## Shipped

### Jervis 7.1 — Voice reliability

Established the public cross-platform Jervis baseline:

- trusted conversation sessions
- longer speaker samples and confidence bands
- retry-before-password identity flow
- continuous voice learning
- conversation lock-on
- local permissions, skills, agents, presence, proactive alerts, timeline, repair, and Control Deck foundations
- native public installer and cross-platform release pipeline

### Jervis 7.3 — Swift runtime

Primary goal: reduce perceived voice-turn latency without turning Jervis into a platform-specific science project.

Shipped:

- Rust/PyO3 acceleration for audio analysis and adaptive VAD in official native builds
- 450 ms configurable command endpointing
- parallel STT + speaker identification
- background STT, speaker, wake, and common-TTS prewarming
- faster OpenClaw Gateway HTTP path with CLI fallback
- leaner SQLite hot path and batched housekeeping
- vectorized speaker matching
- lighter desktop audio buffering and cached Android resampling
- bounded brain context instead of replaying redundant local dialogue
- runtime backend visibility via `jervis runtime-info`

## Shipped — Jervis 7.3.x Hardening

**Status: completed through 7.3.6**

Before adding another large feature layer, 7.3 must be dogfooded as the public product.

Primary work:

- **Benchmarking** — ship `jervis benchmark` for repeatable local DSP/state/context measurements and live turn-latency summaries.
- **Live latency telemetry** — record inference, brain-route, and command-to-reply timings during normal use.
- **Fresh-install dogfood** — install the public release on real target hardware with no repository shortcuts.
- **Soak testing** — long idle periods, repeated wake/follow-up turns, barge-in, speaker learning, and multi-user sessions.
- **Restart/reboot testing** — verify startup and audio recovery after host reboot.
- **Failure testing** — network loss, OpenClaw outage, missing audio device, noisy/quiet microphones, and Android ADB disconnects.
- **7.3.1 policy** — bug fixes, observability, compatibility, and measured latency improvements only. No major feature expansion.

Exit criteria:

- public installer succeeds on the target NUC from a clean state
- no known data-loss or auth-boundary bug
- benchmark output is stable enough to compare builds
- at least one multi-hour soak session without runtime failure
- reboot/startup path is verified
- OpenClaw failure degrades cleanly to local Jervis behavior
- remaining issues are documented before 7.4 begins

### Jervis 7.3.5 — Resilience

Before 7.4, the 7.3 line gains a dedicated recovery layer:

- verified patch self-update with SHA-256 validation
- pre-update binary/state snapshots and rollback
- snapshots before install edits, repairs, migrations, restores, uninstall, and real config edits
- backup/restore
- config and database migration versioning
- crash detection and safe mode
- sanitized diagnostics bundle
- Control Deck Recovery/Repair Center
- uninstall/reinstall cleanup
- interrupted-installer resume journal
- OpenClaw compatibility checks
- post-install acceptance tests
- bounded benchmark history
- explicit permission/capability audit
- dedicated upgrade/rollback CI smoke gate

The purpose of 7.3.5 is not feature expansion; it is to make 7.4 safer to build and easier to recover when experiments go wrong.

## Shipped — Jervis 7.4 “Feels Alive”

**Status: completed in 7.4.0**

Primary goal: make Jervis feel continuous, aware, and contextually present **without pretending to be sentient**.

### Installer rebuild

7.4 replaces the 7.3 Installation Control Deck UI rather than continuing to patch it:

- persistent left-hand setup sidebar on normal terminal sizes
- active setup content in a dedicated right-hand pane
- Desktop and Server are first-class visible choices, not a dropdown
- no animated ASCII hero or constantly repainting decorative shell
- no horizontal numbered step rail
- narrow terminals collapse the sidebar into one compact current-stage label
- installation pages remain scrollable without hiding navigation
- OpenClaw's upstream wizard remains the source of provider/API setup data
- transactional install, snapshots, rollback, diagnostics and recovery remain underneath the new UI

### Continuity

- richer per-user long-term memory with explicit provenance and deletion controls
- conversation/topic continuity across sessions
- better correction handling (“no, I meant…”)
- recency and relevance weighting for memory/context
- compact session summaries instead of replaying full transcripts

### Presence

- stronger entered/left/returned presence model
- multi-user handoff when the active speaker changes
- configurable room/device presence sources
- presence-aware proactive notifications
- suppress interruptions when nobody relevant is present

### Proactive behavior

- priority/expiry for queued notifications
- “tell me when…” local conditions and reminders
- better quiet-hours and cooldown policy
- defer/retry delivery when the user is busy or absent
- explain why a proactive message fired

### Agent orchestration

- clearer task routing between local skills and OpenClaw agents
- explicit agent capability metadata
- cancellable long-running agent actions
- visible action/tool timeline
- safer permission escalation for privileged skills/actions

### Control Deck

- live latency/health dashboard
- memory browser/editor
- presence view
- active agent/tool view
- proactive queue
- benchmark history
- clearer degraded-state and repair controls

7.4 should be developed behind measured 7.3 baselines. A feature that materially worsens normal voice-turn latency needs a documented reason.

## Later — Jervis 7.5+ Ecosystem

Possible direction after 7.4 is stable:

- richer skill packaging/discovery
- MCP server/client management
- external device/room adapters
- plugin permission manifests
- remote Control Deck access with explicit security boundaries
- broader automation/event integrations

## Standing engineering rules

- Measure before and after performance work.
- Prefer the simplest language/runtime for each component; Rust/native code is welcome where it produces a real hot-path benefit.
- Keep portable fallbacks when practical.
- Do not add a local LLM merely to claim “local AI”; local inference must have a concrete latency/privacy/offline goal.
- Every release description must be derived from the actual code diff and document **Added / Changed / Removed / Fixed** behavior.
- Stable release binaries must pass their own runtime/backend verification before publication.
