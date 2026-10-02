# Changelog

All notable public changes to Jervis are documented here.

Release descriptions are derived from actual code diffs and mirrored in `docs/releases/`.

## [7.3.5] - Unreleased

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

## [7.3.0] - Unreleased

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
