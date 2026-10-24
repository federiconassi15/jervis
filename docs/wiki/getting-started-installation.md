# Getting Started: Installation

Jervis 8.0.1 ships native binaries for Linux x64/ARM64, Windows x64, and macOS Intel/Apple Silicon. Fresh installs do not require Python, Node.js or a pre-existing virtual environment.

## Linux / macOS

```sh
curl -fsSL https://raw.githubusercontent.com/federiconassi15/jervis/main/install.sh | sh
```

The bootstrap selects the native binary, verifies its SHA-256 checksum and runs the installer. In 8.0.1 downloaded temporary files and logs are placed inside a private, unpredictable directory and cleaned up when the installer exits.

## Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/federiconassi15/jervis/main/install.ps1 | iex
```

## Setup experience in Jervis 8

The installer uses simple **numbered terminal prompts** for Desktop/Server mode, OpenClaw, audio selection, local owner authentication, and final review. Press Enter for the visible default or q to cancel before installation. Passphrases are masked. Installation uses the same transactional, rollback-backed engine.

Guided OpenClaw onboarding runs through the official `openclaw onboard` CLI separately. The old fullscreen installer is no longer the default.

## First commands

```text
jervis
jervis doctor
jervis status
jervis runtime-info
jervis update-check
jervis benchmark
```

`jervis` opens a plain menu; `jervis legacy-tui` opens the previous Control Deck on capable terminals.

## Upgrades

See [Updates](getting-started-updates.md). The native updater stays on the installed major/minor line unless a cross-line migration is deliberately planned.

## Privacy

Never publish passphrases, credentials, voiceprints, private transcripts, personal filesystem paths or device identifiers.

## Related pages

- [Getting Started index](getting-started-index.md)
- [Installer](installer-index.md)
- [First Run](getting-started-first-run.md)
- [Doctor](getting-started-doctor.md)
