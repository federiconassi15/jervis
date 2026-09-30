# Operations: Doctor

## Scope

This page is the Jervis 7.1 reference for **Doctor** within **Operations**. Jervis is designed as one cross-platform assistant rather than three loosely related ports, so feature behavior is defined by the shared core and translated to each host only where the operating system genuinely differs.

## Expected behavior

Doctor should preserve the Jervis reliability contract: local voice, state, and diagnostics remain available even if the OpenClaw brain, network, model provider, or an optional skill is unavailable. Errors should be visible and recoverable rather than silently wedging the runtime.

Trusted conversation sessions are central to 7.1. A user who has already been confidently recognized or authenticated should remain associated with the conversation while activity continues. Speaker confidence can reinforce the session, but an isolated weak sample does not force immediate reauthentication.

## Platform parity

Linux, Windows, and macOS use the same configuration schema and identity/state model. Host differences are limited to service startup, audio-host APIs, paths, and prerequisite installation. Android AudioSource input is transported by ADB forwarding and feeds the same capture abstraction.

## Server and Desktop

Desktop mode is optimized for the user's normal speakers, microphone, login session, and changing peripherals. Server mode is optimized for persistent startup and explicit hardware. Both modes expose the same Jervis commands, identity logic, OpenClaw routing, Control Deck concepts, and update policy.

## Maintenance

Jervis automated maintenance stays on the current major/minor line. A 7.1.x build may move to a newer 7.1.x patch after validation, but automation must not turn it into 7.2 or 8. External dependency changes should be adapted and tested before pins are updated.

## Security and privacy

Speaker recognition is not strong biometric authentication. Sensitive actions should require appropriate permission and, when necessary, explicit authentication. Logs and examples must not contain API keys, passphrases, voiceprints, private transcripts, device serials, or personal machine details.

## Resource expectations

Jervis targets modest always-on hardware as well as modern desktops. Avoid repeated subprocess launches, hot polling, unbounded history, or eagerly loading expensive speech models. The idle path should remain boring and cheap.

## Diagnostics

Use this order when investigating Doctor:

1. `jervis doctor`
2. Control Deck status and timeline
3. Active Jervis configuration
4. OS service/startup state
5. Audio device state when relevant
6. `openclaw doctor` for brain/provider problems
7. Sanitized logs and a minimal reproduction

## Contribution expectations

A change touching Doctor should include a focused test where practical, at least one failure-case check, and documentation for any changed user-visible behavior. Cross-platform branches should be explicit and small rather than scattering OS checks across core logic.

## Related pages

- [Operations index](operations-index.md)
- [Wiki Home](Home.md)
- [Previous](operations-logs.md)
- [Next](operations-repair.md)
