# Getting Started: Installation

## Public install

Jervis ships self-contained native binaries. The bootstrap detects the host platform, downloads the matching release asset, verifies SHA-256, and launches the native installer.

### Linux / macOS

    curl -fsSL https://raw.githubusercontent.com/federiconassi15/jervis/main/install.sh | sh

### Windows PowerShell

    irm https://raw.githubusercontent.com/federiconassi15/jervis/main/install.ps1 | iex

## What happens next

The native installer opens the Installation Control Deck and walks through deployment mode, OpenClaw, audio, identity, review, and the transactional installation sequence.

In 7.3.1 the bootstrap and installer also use Unicode framing and short terminal-native cues for boot, attention, install start, and completion.

## After installation

    jervis
    jervis doctor
    jervis runtime-info
    jervis benchmark
    jervis benchmark --json

`jervis benchmark` is part of the 7.3.1 hardening line and reports local hot-path measurements plus recent live latency samples when available.

## Privacy

Do not commit credentials, passphrases, raw recordings, voiceprints, private dialogue, device serials, private IP addresses, or personal paths.

## Related pages

- [Getting Started index](getting-started-index.md)
- [Installer](installer-index.md)
- [First Run](getting-started-first-run.md)
- [Doctor](getting-started-doctor.md)
