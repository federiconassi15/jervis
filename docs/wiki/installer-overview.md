# Installer: Overview

Jervis ships one native installer experience across Linux, Windows, and macOS.

## Bootstrap

The public bootstrap selects the correct native asset for the current OS/architecture, downloads `SHA256SUMS`, verifies the binary, and launches the native installer.

Linux/macOS:

    curl -fsSL https://raw.githubusercontent.com/federiconassi15/jervis/main/install.sh | sh

Windows PowerShell:

    irm https://raw.githubusercontent.com/federiconassi15/jervis/main/install.ps1 | iex

## Installation model

The installer is transactional. It stages host changes, verifies them, and preserves rollback boundaries instead of leaving an unknown half-installed state after a failure.

The setup path covers:

1. Desktop or Server deployment
2. OpenClaw setup/authentication mode
3. microphone and output selection
4. owner profile and local authentication
5. final review
6. install + verification

## 7.3.1 presentation

The 7.3.1 hardening line introduces the Unicode-framed **Installation Control Deck** and terminal-native sound cues. This changes presentation/observability, not the transaction model.

Cues use host terminal/console mechanisms only and require no media assets.

## Platform behavior

- Linux startup integrates with systemd where supported.
- Windows uses Task Scheduler for managed per-user startup.
- macOS uses launchd.
- Desktop and Server share the same runtime and config semantics.

## Security

Passphrases, provider credentials, voiceprints, private dialogue, device IDs, and machine-specific private state must never be rendered into public docs/logs or committed to the repo.

## Related pages

- [Installer index](installer-index.md)
- [Installation Control Deck](installer-blue-ui.md)
- [Transaction Model](installer-transaction-model.md)
- [Rollback](installer-rollback.md)
- [Verification](installer-verification.md)
