# Jervis 7.1 Manual Review Checklist

This is a living review checklist for the current 7.1 release candidate. Historical bug lists and old workflow SHAs were removed because they became misleading as soon as the installer and runtime changed.

## Installer

- Native fresh-machine bootstrap does not require Python/Node/Git.
- Downloaded native binaries are SHA-256 verified before execution.
- Linux prerequisite installation occurs inside the Jervis flow, not through a raw `[Y/n]` stdin prompt.
- Wizard navigation works with mouse plus arrow keys.
- Desktop/Server, OpenClaw, audio, owner, review, install, and sign-in stages remain reachable.
- Failed setup restores tracked config/service state.

## Runtime and intelligence

- Wake → acknowledgement → natural command capture works.
- Trusted sessions survive weak/noisy samples without silently authorizing a different person.
- Per-user presence and explicit memory remain isolated.
- Local commands route before skills; permission-checked skills route before OpenClaw.
- Per-user OpenClaw agent choice does not leak to another user.
- OpenClaw failure leaves local Jervis state/diagnostics available.
- Follow-up turns keep a stable per-user OpenClaw session key.

## Audio and identity

- Input/output selection survives startup.
- Audio quality metrics expose RMS, clipping, and quality label.
- Speaker embeddings are bounded and continuously learned only from sufficiently strong, clean matches.
- Jervis asks explicitly how a person wants to be addressed; it does not infer gender from voice.
- Spoken/TUI passphrase paths never persist plaintext credentials.
- Android microphone mode uses the shared ADB locator.

## Features / Control Deck

The Control Deck must expose real data rather than placeholder panels for:

- Dashboard
- Dialogue
- People
- Audio
- Brain
- Skills
- Agents
- Memory
- Permissions
- Timeline
- Logs
- Settings
- Authentication

`jervis doctor` is read-only. `jervis repair audio` and `jervis repair openclaw` are explicit component-scoped repair actions.

## Platform adapters

- Linux: systemd user service
- Windows: Task Scheduler in the interactive user session
- macOS: launchd LaunchAgent in the user session

Do not claim pre-login microphone parity on Windows/macOS when the OS audio/privacy model does not provide it.

## Merge gate

Merge the RC into `main` only when the **latest branch head** is green and the maintainer chooses to release it.
