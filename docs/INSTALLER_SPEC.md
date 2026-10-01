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

1. Bootstrap Jervis with one command.
2. Detect OS, architecture, Python, and basic compatibility.
3. Download the newest stable release on the current 7.1.x line.
4. Verify the release SHA-256.
5. Stage the new version in a versioned directory.
6. Install the package into an isolated environment.
7. Run import and version checks.
8. Launch the Jervis setup wizard.
9. Detect or install OpenClaw.
10. Select Desktop or Server mode.
11. Select microphone and output.
12. Optionally configure Android phone microphone.
13. Create the first owner and authentication passphrase.
14. Configure managed startup.
15. Verify configuration and service health.
16. Commit the installation only after successful setup.

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
- universal jervis-installer.pyz,
- SHA-256 checksum for the installer,
- SHA256SUMS for release assets,
- generated release notes.

Automatic update logic stays on the same major/minor line. A 7.1.x installation never silently becomes 7.2 or 8.


## Native fresh-machine release

The primary public release path does not require a preinstalled Python interpreter. GitHub Actions builds the same Jervis source into self-contained native binaries for Windows x64, Linux x64/ARM64, macOS Intel, and macOS Apple Silicon. The binary is both installer and runtime: first launch copies itself into the stable per-user Jervis location and runs setup; later launches expose the normal Jervis CLI/Control Deck.

The Python zipapp remains a developer/portable fallback, not the fresh-machine requirement.

GitHub Releases also publish one all-platforms ZIP containing all native binaries. A literal shell command cannot be guaranteed identical across stock Windows PowerShell/cmd and POSIX shells because they do not share a command language or downloader; the product-level installer flow and release are nevertheless the same.
