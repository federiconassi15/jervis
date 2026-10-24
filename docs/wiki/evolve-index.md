# Jervis 8.1 — Evolve (development)

**Development documentation:** Jervis 8.1 is under active development in [draft PR #3](https://github.com/federiconassi15/jervis/pull/3). The latest stable release remains **Jervis 8.0.1** until all required gates pass. Do not treat a green branch CI as evidence of an 8.1 release.

Evolve's goal is to make Jervis feel faster and more naturally conversational without sacrificing offline behavior, privacy, or recovery.

## Nine feature tracks

1. [Self-Healing](evolve-self-healing.md): local diagnostics and explicitly consented safe permissions repair.
2. [Better CLI](evolve-better-cli.md): new subcommands and usable terminal help.
3. [Voice Engine 2.0](evolve-voice-engine.md): safe local dialogue routing integrated into voice, with broader voice improvements still in progress.
4. [Control Center](evolve-control-center.md): authenticated, read-only, localhost web dashboard.
5. [Offline Commands](evolve-offline.md): enumerated offline responses, including real local time.
6. [Plugins](evolve-plugins.md): validated manifests and data-only response commands; no arbitrary execution.
7. [Companion Mode](evolve-companion.md): explicitly enabled TLS read-only device pairing; no remote voice or write actions yet.
8. [Encrypted Backups](evolve-encrypted-backups.md): authenticated encrypted exports with password-protected restoration.
9. [HyperCore](evolve-hypercore.md): fast paths, bounded local latency metrics, and repeat-safe conversational response generation.

Read [Security and release gates](evolve-security-and-testing.md) before testing remote connections, recovery, or encrypted restore.

## Compatibility

The draft branch is not a stable distribution. 8.0.1 remains the version users should install. No backward-incompatible configuration migration is approved for Evolve yet. Existing 8.0 settings and services must be preserved through the eventual release.
