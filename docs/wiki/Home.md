# Jervis Wiki

Welcome to the **Jervis 8.0** documentation. The Jervis 8.0.1 patch fixes Linux/macOS bootstrap security and temporary-file cleanup.

**Simple by Default:** `jervis` and `jervis home` open a plain terminal menu. `jervis install` uses numbered prompts with defaults, cancellation and a final review. The old fullscreen Control Deck is opt-in via `jervis legacy-tui`.

Read the [8.0.1 release notes](https://github.com/federiconassi15/jervis/blob/main/docs/releases/8.0.1.md) or visit [GitHub Releases](https://github.com/federiconassi15/jervis/releases) for verified downloads.

## Jervis 8.1 — Evolve development preview

The next feature line is being implemented in [draft PR #3](https://github.com/federiconassi15/jervis/pull/3). The stable release remains **8.0.1**.

Read the [complete Evolve overview](evolve-index.md) and its nine feature pages: [HyperCore](evolve-hypercore.md), [Adaptive Dialogue](evolve-local-dialogue.md), [Voice](evolve-voice-engine.md), [Self-Healing](evolve-self-healing.md), [Better CLI](evolve-better-cli.md), [Control Center](evolve-control-center.md), [Offline Commands](evolve-offline.md), [Plugins](evolve-plugins.md), [Companion](evolve-companion.md) and [Encrypted Backups](evolve-encrypted-backups.md). These pages describe development functionality and outstanding release gates, not claims of a shipped 8.1 version.

## Start here

- [Installation](getting-started-installation.md)
- [Getting Started](getting-started-index.md)
- [CLI Reference](reference-cli.md)
- [Installer](installer-index.md)
- [Voice & Speech](voice-index.md)
- [OpenClaw integration](openclaw-index.md)
- [Control Deck (legacy)](control-deck-index.md)
- [Troubleshooting](troubleshooting-index.md)
- [Development](development-index.md)

## Useful commands

```text
jervis
jervis home
jervis install
jervis run
jervis doctor
jervis status
jervis update-check
jervis legacy-tui
```

## All sections

- [Getting Started](getting-started-index.md)
- [Architecture](architecture-index.md)
- [Audio](audio-index.md)
- [Voice & Speech](voice-index.md)
- [Identity](identity-index.md)
- [OpenClaw](openclaw-index.md)
- [Control Deck (legacy)](control-deck-index.md)
- [Platforms](platforms-index.md)
- [Installer](installer-index.md)
- [Security](security-index.md)
- [State & Memory](state-index.md)
- [Skills](skills-index.md)
- [Agents & MCP](agents-index.md)
- [Operations](operations-index.md)
- [Development](development-index.md)
- [Configuration](configuration-index.md)
- [Troubleshooting](troubleshooting-index.md)
- [Reference](reference-index.md)

## Canonical documents

- [Architecture](../ARCHITECTURE.md)
- [Installer Specification](../INSTALLER_SPEC.md)
- [Cross-platform Compatibility](../CROSS_PLATFORM.md)
- [Privacy](../PRIVACY.md)
- [Roadmap](../ROADMAP.md)

## Documentation history

Many subsystem pages were originally written for Jervis 7.x. They remain useful as *historical technical references*, but may describe interfaces no longer used by default. Consult Installation, CLI Reference, and Versioning for the current 8.0 behavior.

## Product rules

Jervis is one product for Linux, Windows and macOS, with Desktop and Server deployment modes. Never publish credentials, private paths, logs, device identifiers, voiceprints or other personal state. Maintenance stays within the existing major/minor version line.
