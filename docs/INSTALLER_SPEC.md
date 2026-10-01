# Jervis Monster Installer Specification

## One product, two deployment modes

The Jervis installer presents **Desktop** and **Server** as the two installation modes.

### Desktop

Desktop mode is for the computer a person uses day to day. Jervis detects available microphones and speaker/output devices, presents human-readable choices, and lets the user test them during setup. An Android phone may optionally be used as the microphone.

### Server

Server mode is for an always-on NUC, home server, workstation, or headless machine. It installs the same Jervis product with persistent startup, explicit device selection, and remote-friendly operation.

Desktop and Server are independent of operating system.

## Supported operating systems

The public installer targets:

- Linux
- Windows
- macOS

The core behavior must remain shared. OS-specific startup, paths, package prerequisites, and host audio integration belong behind platform adapters.

## Installer identity

The terminal installer uses a clean blue/cyan JARVIS-inspired visual language, tasteful Unicode borders, clear progress indicators, and restrained error colors.

Every launch may show a random lighthearted line near the top, such as:

- Jervis, make me like Tony Stank.
- No arc reactor required.
- Teaching your computer manners.
- Please do not unplug reality.
- One moment, boss.

Cosmetic output must never obscure errors or required user actions.

## Universal install flow

The intended public flow is:

1. Bootstrap Jervis with the stock shell for the operating system.
2. Detect OS, architecture, and basic compatibility without requiring Python or Node.
3. Download the matching self-contained native Jervis binary.
4. Download SHA256SUMS and verify the native binary before execution.
5. Copy the verified native runtime into the stable per-user Jervis location.
6. Launch the Jervis setup wizard.
7. Provision required host prerequisites inside the Jervis flow instead of using pre-TUI stdin prompts.
8. Detect or install OpenClaw.
9. Select Desktop or Server mode.
10. Select microphone and output.
11. Optionally configure Android phone microphone.
12. Create the first owner and authentication passphrase.
13. Configure managed startup.
14. Verify configuration and service health.
15. Commit the installation only after successful setup.

If setup fails, the previous launcher and version pointer are restored.

## OpenClaw integration

OpenClaw is a first-class part of setup.

The Jervis installer:

1. Detects an existing OpenClaw CLI.
2. Reuses it if healthy.
3. Offers to configure it when installed but incomplete.
4. Uses OpenClaw's official installer when it is absent.
5. Hides non-interactive install noise behind the Jervis UI.
6. Returns to Jervis after installation.
7. Exposes the OpenClaw authentication/onboarding step only when user interaction is required.
8. Runs OpenClaw diagnostics before declaring the brain healthy.

Jervis must not fork or silently rewrite OpenClaw internals.

## Audio setup

Desktop mode enumerates host audio devices and shows readable microphone/output choices. The user may run a short speaker tone and microphone level test.

Android microphone mode uses ADB. Jervis forwards the AudioSource Android abstract socket to localhost and reads the raw audio stream directly. This avoids relying on a Linux-only PulseAudio bridge and keeps the transport portable across Linux, Windows, and macOS.

## Identity setup

The first user:

1. enters a display name,
2. chooses whether Jervis should address them as sir or ma'am,
3. creates an authentication passphrase,
4. later trains the local speaker profile.

Jervis does not infer gender from voice.

## Transaction rules

The installer must never modify live state without a rollback story.

Configuration writes are atomic. Existing config/database files are tracked before modification. Managed startup is installed only after first-user state exists. Failed setup restores tracked files and removes newly added service integration where appropriate.

## Release model

Every stable release provides:

- source distribution,
- wheel,
- native binaries for each supported OS/architecture,
- install.sh and install.ps1 native bootstrap scripts,
- SHA256SUMS for release assets,
- generated release notes.

Automatic update logic stays on the same major/minor line. A 7.1.x installation never silently becomes 7.2 or 8.


## Native fresh-machine release

The primary public release path does not require a preinstalled Python interpreter. GitHub Actions builds the same Jervis source into self-contained native binaries for Windows x64, Linux x64/ARM64, macOS Intel, and macOS Apple Silicon. The binary is both installer and runtime: first launch copies itself into the stable per-user Jervis location and runs setup; later launches expose the normal Jervis CLI/Control Deck.

Source installs remain available for developers, but are not part of the fresh-machine installation path. The public bootstrap must never require a preinstalled Python runtime.\n

## Input model

Normal installer navigation uses the mouse or arrow keys. The installer must not require Tab, Enter, letter hotkeys, or a raw terminal yes/no prompt to move through setup. Text entry is reserved for values that are intrinsically textual, such as a person's name, a passphrase, or provider credentials handed off to OpenClaw.
