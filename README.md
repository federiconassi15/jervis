# Jervis

> A lightweight, cross-platform, always-on voice assistant powered by OpenClaw.

Jervis 7.1 is a local voice shell for Linux, Windows, and macOS. It combines wake-word handling, trusted conversation sessions, local identity/state, a terminal Control Deck, optional Android-phone microphone input, and an OpenClaw agentic brain.

## Install

### Fresh machine — recommended

Jervis does **not** require Python, Node.js, pip, npm, Git, or a pre-created virtual environment. Stable releases ship self-contained native Jervis binaries.

The bootstrap scripts only detect the OS/CPU, download the matching native release, verify its SHA-256 checksum, and launch it. Jervis then provisions the host pieces it actually needs.

#### Linux / macOS

Normal Linux/macOS:

    curl -fsSL https://raw.githubusercontent.com/federiconassi15/jervis/main/install.sh | sh

Bare Arch Linux (no Python, Node, Git, curl, or wget preinstalled):

    pacman -Sy --needed --noconfirm curl ca-certificates && curl -fsSL https://raw.githubusercontent.com/federiconassi15/jervis/main/install.sh | sh

The bootstrap itself uses only the host shell and native OS facilities. Once started, `install.sh` can provision its own downloader through pacman, apt, dnf, zypper, or apk when curl/wget is absent. A network installer cannot literally fetch bytes without either a stock downloader or the OS package manager, so Jervis deliberately depends on neither Python nor another language runtime.

#### Windows

PowerShell is built into supported Windows installs:

    irm https://raw.githubusercontent.com/federiconassi15/jervis/main/install.ps1 | iex

### What the installer does

The native installer:

- detects Desktop vs Server setup,
- installs missing Linux audio prerequisites when required,
- detects or installs OpenClaw,
- lets you choose microphone/output devices,
- supports an Android phone as a microphone,
- creates the first owner profile and local authentication passphrase,
- installs managed startup,
- verifies health before committing the install,
- rolls back failed installation changes instead of leaving a half-install.

Installer navigation is designed around **arrow keys and mouse input**. Text entry is only used where actual text is unavoidable, such as the owner name or passphrase.

### Manual native downloads

You can also download a verified release binary directly:

- Windows x64: `jervis-windows-x64.exe`
- Linux x64: `jervis-linux-x64`
- Linux ARM64: `jervis-linux-arm64`
- macOS Apple Silicon: `jervis-macos-arm64`
- macOS Intel: `jervis-macos-x64`

The release also includes `SHA256SUMS` and both bootstrap scripts.

### Developer install

Python 3.11+ is only required for source development and tests:

    python -m pip install -e ".[dev]"

## Desktop or Server

Desktop mode detects microphones and speakers on the everyday computer and asks which ones Jervis should use. An Android phone can optionally be selected as the microphone.

Server mode installs the same product as a persistent always-on assistant for a NUC, home server, workstation, or other long-running machine.

## OpenClaw

OpenClaw setup is integrated into the Jervis installer. Existing installations are reused. If OpenClaw is missing, Jervis runs OpenClaw's official installer and exposes only the authentication/onboarding step that genuinely needs user input. OpenClaw provisions its own supported Node runtime when needed.

## Voice flow

    Jervis
      ↓
    Boss?
      ↓
    full natural command
      ↓
    speaker identity + trusted session
      ↓
    local route / skill / OpenClaw
      ↓
    response + follow-up conversation

Jervis 7.1 identifies from the longer natural command rather than trying to authenticate a person from the wake word alone.

## Commands

    jervis
    jervis run
    jervis doctor
    jervis install
    jervis repair audio
    jervis repair openclaw
    jervis update-check

## Wiki

Canonical technical docs:

- [Architecture](docs/ARCHITECTURE.md)
- [Monster Installer Specification](docs/INSTALLER_SPEC.md)
- [Cross-platform Compatibility](docs/CROSS_PLATFORM.md)
- [Privacy](docs/PRIVACY.md)
- [Roadmap](docs/ROADMAP.md)

## Platforms

Linux, Windows, and macOS share the same core and configuration schema. OS-specific startup and device behavior live behind platform adapters.

## Security

Speaker recognition is a convenience identity signal, not strong authorization for sensitive actions. Authentication passphrases are stored as PBKDF2-HMAC-SHA256 verifiers rather than plaintext.

## License

GNU General Public License v3.0 or later. See LICENSE.

## Credits

Created by Federico Nassi with AI-assisted development, debugging, architecture work, testing, and documentation.

Jervis is not affiliated with Marvel, Iron Man, or any related trademark holder.
