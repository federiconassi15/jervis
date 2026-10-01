# Jervis 7.1 Manual Critical-File Review

Stage **#7/8** was performed on the public release-candidate branch after the
automated validation stage.

Reviewed head before this record:

`2951f174aa7cb6dd2f93d28fd2dde9b31287ee43`

## Files reviewed directly

The critical pass covered:

- universal downloader and bootstrap
- transactional installer and rollback
- OpenClaw discovery, official installation handoff, authentication and doctor
- Linux systemd integration
- Windows Task Scheduler integration
- macOS launchd integration
- configuration validation and platform paths
- runtime wake / command / follow-up loop
- trusted identity sessions
- speaker embedding model download and verification
- speaker recognition confidence handling
- spoken and TUI authentication
- dialogue and event persistence
- Android ADB audio input
- desktop audio input
- selected-output TTS and Jervis-only volume
- Control Deck Dialogue, People, Audio, Timeline and Authentication panels
- same-minor patch update discovery
- release artifact builder and verifier
- repository verifier and CI workflow

## Release blockers found and fixed

The manual pass found issues that syntax-only checking would not have caught:

1. **Selected output and Jervis volume were not connected to speech playback.**
   TTS now renders speech to PCM and plays it through the selected output using
   Jervis's own 5%-200% volume setting.

2. **Authentication and Dialogue Control Deck panels were placeholders.**
   They now provide local password verification, identity selection/new-user
   creation, timestamped dialogue, Unknown/Jervis/user labels and live activity.

3. **Unknown-speaker authentication was incomplete.**
   The runtime now accepts a short-lived TUI authentication grant or the spoken
   passphrase flow, establishes a trusted session, and performs new-user voice
   training/address preference when needed.

4. **Trusted sessions did not roll their absolute expiry forward.**
   Active conversation now refreshes both inactivity time and trust lifetime.

5. **Android audio ignored read timeouts.**
   Socket timeout is now honored and translated into the same queue-empty
   behavior as desktop capture.

6. **Android runtime could lose ADB after an installer-only PATH discovery.**
   Runtime capture now uses the same cross-platform ADB locator as setup.

7. **The speaker embedding backend had no fresh-install model acquisition.**
   Setup now downloads the pinned WeSpeaker ResNet34 model, verifies its
   SHA-256 and retains a functional auth/session fallback if download fails.

8. **OpenClaw could be installed outside the current PATH but later appear
   missing to the runtime.**
   Runtime and doctor now share the installer's OpenClaw discovery logic.

9. **Linux could have PortAudio while still lacking a TTS renderer.**
   PortAudio and espeak-ng prerequisites are now checked independently.

10. **Reinstall startup changes were not fully reconciled.**
    Desktop/Server/autostart changes now replace the prior startup registration
    transactionally, with a rollback callback that restores the previous
    registration after failure.

11. **Windows server startup originally targeted a non-interactive SYSTEM
    session.**
    Jervis 7.1 keeps the voice runtime in the interactive user's audio session,
    because microphone/speaker parity is more important than pretending
    Session-0 audio is equivalent.

12. **macOS server startup originally used a system LaunchDaemon.**
    It now uses a persistent LaunchAgent in the logged-in CoreAudio/TCC session
    so microphone permission and selected audio devices remain available.

13. **Windows Task Scheduler command quoting had a path-with-spaces edge case.**
    The command argument is now generated deterministically and covered by a
    regression test using a Windows path containing spaces.

14. **Patch update discovery used GitHub's global latest release.**
    It now searches stable releases and chooses the newest release on the
    current major/minor line, so a newer 7.2 release cannot hide a 7.1 patch.

15. **AEC documentation overstated current behavior.**
    Jervis 7.1 now explicitly leaves AEC disabled instead of calling
    post-playback queue flushing acoustic echo cancellation.

## Cross-platform verification after fixes

GitHub Actions run **36812818583** completed successfully for the reviewed
code head:

- Ubuntu latest / Python 3.11 — PASS
- Ubuntu latest / Python 3.13 — PASS
- Windows latest / Python 3.11 — PASS
- Windows latest / Python 3.13 — PASS
- macOS latest / Python 3.11 — PASS
- macOS latest / Python 3.13 — PASS
- Universal release artifact — PASS

The workflow includes Python compilation, repository parsing/encoding/link
verification, smoke tests, unit tests, Ruff correctness checks, package build,
universal installer build and release-artifact verification.

## Explicit scope boundaries

These are documented behavior, not hidden claims:

- Jervis 7.1 does **not** claim live acoustic echo cancellation. The setting is
  off by default until a synchronized far-end-reference implementation is
  integrated and validated cross-platform.
- Windows Server mode and macOS Server mode keep the voice runtime in the
  logged-in user's interactive audio session. They are persistent voice-server
  modes, not pre-login system audio services.
- Speaker recognition is convenience identity, not high-assurance biometric
  authentication. Sensitive actions should still use explicit permission/auth
  escalation.
- A successful review cannot mathematically prove non-trivial software has zero
  bugs; it records the release gates and concrete checks performed.

## Merge gate

Stage #8 may merge the RC branch to `main` only after the branch remains
green and the maintainer explicitly chooses to proceed.
