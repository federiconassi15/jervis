# Jervis

> A lightweight, cross-platform, always-on voice assistant powered by OpenClaw.

Jervis 7.3.5 is a low-latency, rollback-aware local voice shell for Linux, Windows, and macOS. It combines wake-word handling, trusted conversation sessions, local identity/state, a terminal Control Deck, optional Android-phone microphone input, and an OpenClaw agentic brain. Native releases use a Rust-accelerated audio/VAD hot path while retaining a portable NumPy fallback for source installs.

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

Jervis identifies from the longer natural command rather than trying to authenticate a person from the wake word alone. In 7.3 the runtime prewarms speech/identity models, uses faster command endpointing, batches state work, and can talk to the local OpenClaw Gateway directly when its authenticated HTTP surface is available.

## Commands

    jervis
    jervis run
    jervis doctor
    jervis install
    jervis repair audio
    jervis repair openclaw
    jervis update-check
    jervis update
    jervis update --rollback
    jervis status
    jervis repair-center
    jervis repair all
    jervis snapshot create
    jervis snapshot list
    jervis snapshot restore <id>
    jervis backup create <file>
    jervis backup restore <file>
    jervis doctor --bundle
    jervis permissions
    jervis acceptance-test
    jervis run --safe-mode
    jervis runtime-info
    jervis benchmark
    jervis benchmark --json

## 7.3.5 resilience + rollback

7.3.5 is the final resilience-focused 7.3.x pass before larger 7.4 experience work.

- verified native self-update on the current 7.3 patch line,
- SHA-256 validation before binary replacement,
- automatic pre-update snapshots with binary rollback,
- state snapshots before install/reconfigure, repair, migration, restore, uninstall, and real config edits,
- manual snapshot create/list/restore commands,
- backup/export and restore with a pre-restore guard snapshot,
- versioned config and SQLite schema migration foundations,
- crash markers with automatic safe-mode escalation after repeated unclean runs,
- explicit `jervis run --safe-mode` that disables proactive work, skills, and OpenClaw routing,
- `jervis status` terminal health dashboard,
- Control Deck **RECOVERY** tab and `jervis repair-center`,
- snapshot-backed repair for audio, OpenClaw, startup, database, models, and permissions,
- sanitized diagnostics bundles with secret and home-path redaction,
- installer resume journal after interrupted setup,
- post-install acceptance checks,
- OpenClaw Gateway-RPC compatibility probe,
- bounded benchmark history,
- real uninstall/reinstall paths,
- explicit permission/capability audit,
- dedicated upgrade + rollback smoke gate in CI.

Snapshots focus on mutable Jervis state. Re-downloadable model/tool caches are preserved in place rather than duplicated into every snapshot.

See [7.3.5 release notes](docs/releases/7.3.5.md).

## 7.3.1 runtime + hardening

The 7.3 runtime is optimized around lower voice-turn latency, while 7.3.1 adds hardening, benchmarking, and a more expressive terminal-native setup experience:

- optional Rust/PyO3 audio analysis and adaptive VAD,
- 450 ms configurable end-of-command silence endpointing,
- background Whisper, speaker, wake, and common-TTS prewarming,
- cached/vectorized speaker matching,
- lighter desktop audio buffering and cached Android resampling,
- SQLite WAL/NORMAL state with batched retention housekeeping,
- OpenClaw Gateway HTTP fast path with safe CLI fallback,
- `jervis runtime-info` to show the active acceleration backend,
- `jervis benchmark` for local and recent live latency measurements,
- Unicode-framed installation Control Deck with terminal-native BEL/console cues for boot, attention, install start, and completion.
- OpenClaw's live onboarding wizard rendered inside Jervis, so provider/API/plugin support follows the installed OpenClaw version instead of a Jervis-maintained list.

See [7.3.1 release notes](docs/releases/7.3.1.md) for the current code-derived change list and [7.3.0 release notes](docs/releases/7.3.0.md) for the original 7.3 runtime rebuild.

### Hardening / benchmarking

The 7.3.x hardening line adds repeatable measurements before 7.4 feature work:

    jervis benchmark
    jervis benchmark --iterations 250 --history 200
    jervis benchmark --json

The synthetic section measures the local DSP, SQLite write/read, and brain-context snapshot paths on the current machine. The live section summarizes recent real `inference_ms`, `brain_ms`, and `command_to_reply_ms` samples recorded during normal voice use.

See [Dogfood & Soak Plan](docs/DOGFOOD.md) and the updated [Roadmap](docs/ROADMAP.md).

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
