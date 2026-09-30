# Jervis Wiki

Welcome to the Jervis 7.1 in-repository wiki.

This wiki contains **381 pages** covering the complete public Jervis product: installation, cross-platform architecture, audio, speech, identity, trusted sessions, OpenClaw, the Control Deck, platform behavior, security, memory, skills, agents, operations, development, configuration, troubleshooting, and reference material.

## Start here

- New user: [Getting Started](getting-started-index.md)
- Installer details: [Installer](installer-index.md)
- Voice reliability: [Voice & Speech](voice-index.md)
- Speaker identity: [Identity](identity-index.md)
- OpenClaw integration: [OpenClaw](openclaw-index.md)
- Debugging: [Troubleshooting](troubleshooting-index.md)
- Developer reference: [Development](development-index.md)

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
- [Monster Installer Specification](../INSTALLER_SPEC.md)
- [Cross-platform Compatibility](../CROSS_PLATFORM.md)
- [Privacy](../PRIVACY.md)
- [Roadmap](../ROADMAP.md)

## Product rules

Jervis 7.1 is one product across Linux, Windows, and macOS. Desktop and Server are deployment modes, not separate editions. The same core owns identity, trusted sessions, permissions, state, skills, and OpenClaw routing.

The public build must remain generic. Do not place private IP addresses, personal filesystem paths, authentication secrets, device serial numbers, private transcripts, or user-specific voiceprints in the repository.

Automated maintenance may increment only the patch number on the current 7.1.x line.
