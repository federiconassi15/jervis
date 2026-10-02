# Jervis Wiki

Welcome to the Jervis **7.3** documentation.

The current stable release is **7.3.0**. **7.3.1 hardening is in development** and adds benchmarking, live latency telemetry, installer polish, terminal-native cues, and a formal dogfood/soak-test gate before 7.4.

## Start here

- New user: [Getting Started](getting-started-index.md)
- Install Jervis: [Installation](getting-started-installation.md)
- Installer internals and UX: [Installer](installer-index.md)
- Voice & latency: [Voice & Speech](voice-index.md)
- Speaker identity: [Identity](identity-index.md)
- OpenClaw integration: [OpenClaw](openclaw-index.md)
- Control Deck: [Control Deck](control-deck-index.md)
- Debugging: [Troubleshooting](troubleshooting-index.md)
- Developer reference: [Development](development-index.md)

## 7.3.1 hardening

The 7.3.1 line is intentionally focused on proving the 7.3 runtime before larger 7.4 work.

Highlights:

- `jervis benchmark` for synthetic and recent live latency measurements
- runtime metrics for inference, brain routing, and command-to-reply latency
- public-install dogfood and soak-test checklist
- Unicode-framed Installation Control Deck
- terminal-native boot, attention, install-start, and completion cues
- no bundled sound assets or extra audio dependency

## All sections

- [Getting Started](getting-started-index.md)
- [Architecture](architecture-index.md)
- [Audio](audio-index.md)
- [Voice & Speech](voice-index.md)
- [Identity](identity-index.md)
- [OpenClaw](openclaw-index.md)
- [Control Deck](control-deck-index.md)
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

## Canonical project documents

- [Architecture](../ARCHITECTURE.md)
- [Installer Specification](../INSTALLER_SPEC.md)
- [Cross-platform Compatibility](../CROSS_PLATFORM.md)
- [Privacy](../PRIVACY.md)
- [Roadmap](../ROADMAP.md)

## Product rules

Jervis is one product across Linux, Windows, and macOS. Desktop and Server are deployment modes, not separate editions.

The public build must remain generic. Never commit private IP addresses, personal filesystem paths, credentials, device serials, private transcripts, voiceprints, or machine-specific personal tailoring.

Automated maintenance stays on the current major/minor line and may only advance the patch version after validation.
