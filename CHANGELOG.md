# Changelog

All notable public changes to Jervis are documented here.

## [7.1.1] - 2026-10-01

### Added

- Cross-platform Jervis 7.1 runtime for Linux, Windows, and macOS.
- Desktop and Server install modes.
- Integrated OpenClaw installation and onboarding.
- Trusted conversation sessions and full-command speaker identification.
- "Boss?" wake acknowledgement.
- Android AudioSource microphone support through ADB.
- Mouse-friendly blue terminal installer and Control Deck.
- Native no-Python-required binaries for Windows x64, Linux x64/ARM64, macOS Intel, and macOS Apple Silicon.
- Universal Python release artifact and all-platforms release ZIP.
- 381-page in-repository wiki.
- Cross-platform CI, release checks, diagnostics, updater, skills, agents, permissions, and resilience foundations.

### Fixed

- Repeated speaker-authentication loops during normal conversations.
- Cross-platform service/startup behavior.
- Windows task quoting and macOS interactive audio-session behavior.
- OpenClaw detection after installation.
- Android ADB discovery and audio timeouts.
- Selected-output TTS and Jervis-specific volume handling.
- Installer rollback and fresh-machine prerequisite handling.

## [7.1.0] - 2026-10-01

- Initial public Jervis 7.1 release scaffold and publication workflow.
