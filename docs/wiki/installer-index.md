# Installer

Jervis uses one native installer experience across Linux, Windows, and macOS.

## 7.3.1 Installation Control Deck

The 7.3.1 installer keeps the existing transactional install engine but presents it as a Unicode-framed terminal control deck:

1. Deployment Mode
2. OpenClaw Brain
3. Audio Matrix
4. Identity Core
5. Final Review
6. Installation Sequence

Major states use boxed terminal status panels rather than plain prose. Completion branding always uses the active Jervis version.

### Terminal-native cues

The installer uses terminal/console-generated cues, not media files:

- boot: short double cue
- install start: rising double cue
- attention/error/sign-in required: stronger three-part cue
- completion: short success chirp

Windows uses console frequency beeps when available. Linux/macOS use terminal BEL. A terminal may render BEL audibly, visually, or ignore it.

Disable cues:

    JERVIS_TERMINAL_CUES=0

Force them in a nonstandard terminal:

    JERVIS_FORCE_TERMINAL_CUES=1

## Pages

- [Overview](installer-overview.md)
- [Control Deck UI](installer-blue-ui.md)
- [Banter & Cues](installer-banter.md)
- [Preflight](installer-preflight.md)
- [OS Detection](installer-os-detection.md)
- [Hardware Detection](installer-hardware-detection.md)
- [Mode Selection](installer-mode-selection.md)
- [Audio Selection](installer-audio-selection.md)
- [Android Selection](installer-android-selection.md)
- [OpenClaw Install](installer-openclaw-install.md)
- [Config Generation](installer-config-generation.md)
- [Service Install](installer-service-install.md)
- [Transaction Model](installer-transaction-model.md)
- [Rollback](installer-rollback.md)
- [Verification](installer-verification.md)
- [Source Install](installer-source-install.md)
- [Offline Limits](installer-offline-limits.md)
- [Repair Mode](installer-repair-mode.md)
- [Troubleshooting](installer-troubleshooting.md)

[Back to Wiki Home](Home.md)
