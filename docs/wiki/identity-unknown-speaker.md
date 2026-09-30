# Identity: Unknown Speaker

## Purpose

This page documents **Unknown Speaker** in the **Identity** subsystem of Jervis 7.1. The public Jervis build is one product across Linux, Windows, and macOS, with Desktop and Server deployment modes sharing the same core runtime and configuration model.

## How it works

Jervis keeps OS-specific behavior behind platform adapters while the voice loop, identity sessions, permissions, state, skills, and OpenClaw routing remain shared. Unknown Speaker should therefore behave consistently even when the host operating system uses a different audio API, startup manager, or filesystem convention.

For the 7.1 reliability line, the default interaction is: wake word → **Boss?** acknowledgement → capture the full natural command → evaluate the trusted session and speaker evidence → route locally or through OpenClaw → keep the same speaker locked through the follow-up window.

## Desktop and Server behavior

**Desktop mode** uses the user's normal computer audio devices. Setup enumerates available microphones and outputs and asks which ones Jervis should use. An Android phone may be selected as the microphone.

**Server mode** uses the same runtime but emphasizes persistent startup, explicit device choices, and remote-friendly diagnostics. It is suitable for a NUC, home server, workstation, or other always-on machine.

## Cross-platform notes

- **Linux:** managed startup uses a systemd user service where available.
- **Windows:** per-user managed startup uses Task Scheduler.
- **macOS:** managed startup uses launchd.
- Desktop audio is exposed through the host PortAudio backend.
- Android AudioSource uses ADB forwarding to a localhost TCP socket, so the Jervis-side transport is shared across all three operating systems.

## Reliability rules

1. Do not turn one noisy voice sample into an authentication loop.
2. Keep expensive speech and speaker models lazy where practical.
3. Bound histories, queues, caches, and stored embeddings.
4. Repair the smallest failed component before restarting the whole runtime.
5. Keep the local shell useful when OpenClaw or a model provider is unavailable.
6. Treat speaker recognition as a convenience identity signal, not high-assurance security.

## Privacy and security

Never commit provider credentials, authentication passphrases, voiceprints, raw recordings, private dialogue, Android serial numbers, private IP addresses, or personal filesystem paths. Jervis stores authentication passphrases as PBKDF2-HMAC-SHA256 verifiers rather than plaintext. Raw microphone audio is not intended to be persisted by default.

## Diagnostics

Start with `jervis doctor`. For agentic-brain problems, also use `openclaw doctor`. The Control Deck timeline should show wake, identity, routing, provider, and repair events with timestamps so failures can be diagnosed without guessing.

When debugging Unknown Speaker, verify configuration and selected devices before changing recognition thresholds. Threshold changes should be a last step after confirming that audio quality and session state are healthy.

## Development checklist

- Test the normal path.
- Test at least one failure path.
- Consider Windows, macOS, and Linux behavior.
- Consider Desktop and Server modes.
- Avoid blocking or hot-polling work in the always-on loop.
- Avoid logging secrets or authentication text.
- Preserve rollback and doctor behavior when setup files change.

## Related pages

- [Identity index](identity-index.md)
- [Wiki Home](Home.md)
- [Previous](identity-uncertain-retry.md)
- [Next](identity-trusted-sessions.md)
