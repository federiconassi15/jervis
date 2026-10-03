# Changelog

All notable public changes to Jervis are documented here.

Release descriptions are derived from actual code diffs and mirrored in `docs/releases/`.

## [7.4.0] - 2026-10-02

### Added

- Rebuilt installer and Control Deck navigation around a responsive sidebar with narrow-terminal fallbacks.
- Query-aware memory, rolling session summaries, memory provenance/importance, and correction-aware context.
- Presence history, active-speaker handoff tracking, proactive reminders/condition watches, and busy-window handling.
- Agent capability/run history, cancellable long-running agent execution, permission-escalation records, and action timelines.
- Control Deck views for memory, presence, proactive work, agents, benchmarks, and recovery controls.

### Changed

- Replaced the 7.3 animated installer shell and horizontal setup rail with semantic sidebar stages and independently scrollable pages.
- Context retrieval now ranks memories against the current request and prefers compact session summaries over full transcript replay.
- Presence-aware proactive delivery queues work while users are away or busy.
- Long-running OpenClaw CLI calls use a cancellable process-tree path while normal low-thinking HTTP calls retain the latency fast path.

### Removed

- The 7.3 installer hero animation and horizontal numbered subsystem rail.
- Desktop/Server deployment dropdown as the primary mode selector.
- Silent skipping of matched privileged skills that provide a safe matcher.

### Fixed

- Server mode is visible immediately during deployment selection.
- Installer and Control Deck navigation remain usable across live terminal resizing.
- Agent cancellation terminates the relevant process tree instead of only a wrapper process.
- Condition watches only announce after their predicate becomes true, and expired proactive work is retired.
- Privileged skill matches can explain required permission without executing the handler.

## [7.3.6] - 2026-10-02

### Added

- Responsive installer modes for normal, compact, and tiny terminals with live resize handling.
- Regression coverage for wide-to-narrow-to-wide installer resizing.
- Quiet Linux dependency execution with bounded failure output.

### Changed

- POSIX and Windows bootstrap downloads use quiet transfer behavior with Jervis-owned status messages.
- Linux prerequisite installation uses quiet package-manager operation after interactive sudo authentication.
- Installer framing, headings, hero, step rail, and navigation controls adapt to available terminal dimensions.

### Removed

- Public curl transfer meters and successful package-manager transaction noise.
- Reliance on fixed-width decorative headings for core installer navigation.

### Fixed

- Live SSH/terminal resizing no longer leaves the installer using stale desktop-scale dimensions.
- Small terminals retain a reachable, scrollable page viewport and bottom navigation.
- Package-manager failures remain visible as concise actionable tails.

## [7.3.5] - 2026-10-02

### Added

- Snapshot rollback system for updates, repairs, install changes, config edits/migrations, restore, and uninstall.
- Verified native self-update with SHA-256 validation and binary rollback.
- Backup/restore, crash recovery, safe mode, diagnostics bundle, Repair Center, status dashboard, permission audit, post-install acceptance checks, install resume journal, benchmark history, and OpenClaw compatibility probing.
- Upgrade + rollback smoke tests in CI.

### Changed

- Config schema is versioned at schema 2 with recovery defaults.
- SQLite now records an explicit schema version.
- Repairs, reinstall, and destructive maintenance paths are snapshot-backed.

### Fixed

- Windows binary rollback/update replacement is deferred safely until process exit.
- Backup restore preserves snapshot identity.
- Mutable-state restore preserves model/tool caches.

## [7.3.0] - 2026-10-02

### Added

- Optional Rust/PyO3 acceleration for audio analysis and VAD, with NumPy fallback.
- OpenClaw Gateway HTTP fast transport with CLI fallback.
- Bounded memory context with redundant recent-dialogue prompt replay disabled by default.
- Background STT, speaker, wake, and common-TTS prewarming.
- Parallel STT + speaker-identification inference for command turns.
- Batched brain context snapshots and transport telemetry.
- 7.3 fast-path regression tests.
- `jervis runtime-info` to expose the active acceleration backend.

### Changed

- Rebuilt SQLite hot-path behavior around WAL/NORMAL, periodic pruning, and cached embeddings.
- Switched normal Whisper decoding to a beam-1 low-latency profile and longer warm retention.
- Vectorized speaker matching.
- Replaced desktop microphone `queue.Queue` buffering with a lighter condition/deque.
- Cached Android resampling axes, activity writes, volume reads, CLI discovery, and barge-in leakage baseline.
- Reduced configurable end-of-command silence endpoint from the old fixed 750 ms to 450 ms by default.

### Removed

- Repeated per-turn SQLite pruning scans.
- Repeated OpenClaw CLI path discovery.
- Repeated per-embedding normalization/JSON parsing in speaker matching.
- Redundant Whisper VAD after Jervis capture VAD.
- Desktop audio `queue.Queue` hot-path overhead.

### Fixed

- Retention batching still honors very small configured history limits.
- Transport telemetry remains compatible with non-OpenClaw test brains.
- Compact-terminal nav overflow inherited from the 7.1 installer.
- PyInstaller native binaries now explicitly bundle the compiled Rust extension instead of losing it during freezing.

## [7.1.1] - 2026-10-01

### Added

- Cross-platform Jervis 7.1 runtime for Linux, Windows, and macOS.
- Desktop and Server install modes.
- Integrated OpenClaw installation and onboarding.
- Trusted conversation sessions and full-command speaker identification.
- "Boss?" wake acknowledgement.
- Android AudioSource microphone support through ADB.
- Mouse-friendly blue terminal installer and Control Deck.
- Native no-Python-required binaries for Windows x64, Linux x64/ARM64, macOS Intel, and macOS Apple Silicon.
- Universal Python release artifact and all-platforms release ZIP.
- 381-page in-repository wiki.
- Cross-platform CI, release checks, diagnostics, updater, skills, agents, permissions, and resilience foundations.

### Fixed

- Repeated speaker-authentication loops during normal conversations.
- Cross-platform service/startup behavior.
- Windows task quoting and macOS interactive audio-session behavior.
- OpenClaw detection after installation.
- Android ADB discovery and audio timeouts.
- Selected-output TTS and Jervis-specific volume handling.
- Installer rollback and fresh-machine prerequisite handling.

## [7.1.0] - 2026-10-01

- Initial public Jervis 7.1 release scaffold and publication workflow.
