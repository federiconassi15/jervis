# Jervis

> A lightweight, cross-platform, always-on voice assistant powered by OpenClaw.

Jervis 7.1 is a local voice shell for Linux, Windows, and macOS. It combines wake-word handling, trusted conversation sessions, local identity/state, a terminal Control Deck, optional Android-phone microphone input, and an OpenClaw agentic brain.

## Install

### Fresh machine — recommended

**Python is not required. Node.js is not required in advance.** Stable releases contain self-contained native Jervis binaries with the Python runtime bundled inside.

Open the latest [GitHub Release](https://github.com/federiconassi15/jervis/releases/latest) and download the matching file:

- Windows x64: `jervis-windows-x64.exe`
- Linux x64: `jervis-linux-x64`
- Linux ARM64: `jervis-linux-arm64`
- macOS Apple Silicon: `jervis-macos-arm64`
- macOS Intel: `jervis-macos-x64`

Run the downloaded binary. On its first launch it opens the same blue Jervis installer, copies the verified native runtime into the user's Jervis data directory, and configures the operating-system startup integration.

The release also contains **`jervis-installer-all-platforms.zip`**, one download containing every native build.

### Command-line download

A stock Windows shell and a POSIX shell do not share one guaranteed command language or downloader, so there is no honest literal one-liner that can execute unchanged on every freshly installed Windows, macOS, and Linux system. Jervis therefore provides native release binaries that require no language runtime.

Windows PowerShell:

    iwr https://github.com/federiconassi15/jervis/releases/latest/download/jervis-windows-x64.exe -OutFile jervis.exe; .\jervis.exe

macOS Apple Silicon:

    curl -fL https://github.com/federiconassi15/jervis/releases/latest/download/jervis-macos-arm64 -o jervis && chmod +x jervis && ./jervis

Linux x64:

    curl -fL https://github.com/federiconassi15/jervis/releases/latest/download/jervis-linux-x64 -o jervis && chmod +x jervis && ./jervis

### Python / developer install

Python 3.11+ users can still use the universal source bootstrap or `jervis-installer.pyz` from Releases.

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
    jervis update-check

## Wiki

The in-repository Jervis wiki contains **381 pages** of installation, architecture, audio, voice, identity, OpenClaw, Control Deck, platform, security, state, skills, agents, operations, development, configuration, troubleshooting, and reference documentation.

Start here: [Jervis Wiki Home](docs/wiki/Home.md)

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
