# Jervis

> A lightweight, cross-platform, always-on voice assistant powered by OpenClaw.

Jervis 7.1 is a local voice shell for Linux, Windows, and macOS. It combines wake-word handling, trusted conversation sessions, local identity/state, a terminal Control Deck, optional Android-phone microphone input, and an OpenClaw agentic brain.

## Install

Jervis requires Python 3.11 or newer.

The same one-command bootstrap works from PowerShell, Command Prompt, Terminal, bash, and zsh:

    python -c "import urllib.request;exec(urllib.request.urlopen('https://raw.githubusercontent.com/federiconassi15/jervis/main/install.py').read())"

The bootstrap selects the newest stable 7.1.x release, downloads the universal jervis-installer.pyz asset, verifies its SHA-256, and launches it with the current Python interpreter.

You can also download jervis-installer.pyz directly from a GitHub release and run:

    python jervis-installer.pyz

## Desktop or Server

Desktop mode detects the microphones and speakers on the everyday computer and asks which ones Jervis should use. An Android phone can optionally be selected as the microphone.

Server mode installs the same product as a persistent always-on assistant for a NUC, home server, workstation, or other long-running machine.

## OpenClaw

OpenClaw setup is integrated into the Jervis installer. Existing installations are reused. If OpenClaw is missing, Jervis can run its official installer quietly and then expose only the authentication/onboarding step that needs user input.

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

## Platforms

Linux, Windows, and macOS share the same core and configuration schema. OS-specific startup and device behavior live behind platform adapters.

## Security

Speaker recognition is a convenience identity signal, not strong authorization for sensitive actions. Authentication passphrases are stored as PBKDF2-HMAC-SHA256 verifiers rather than plaintext.

## License

GNU General Public License v3.0 or later. See LICENSE.

## Credits

Created by Federico Nassi with AI-assisted development, debugging, architecture work, testing, and documentation.

Jervis is not affiliated with Marvel, Iron Man, or any related trademark holder.
