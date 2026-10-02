# Installer: Banter & Terminal Cues

## Purpose

Jervis uses small bits of terminal personality during setup without depending on media files or a desktop notification system.

## Banter

Short rotating lines such as “Local. Fast. Yours.” provide atmosphere while keeping the installer readable. Banter is cosmetic and never replaces an actionable error or status message.

## Terminal cues

7.3.1 defines four short cue classes:

- **boot** — installer/control deck becomes active
- **install** — the transactional installation sequence begins
- **attention** — validation failure, install failure, or required OpenClaw sign-in
- **complete** — verified installation finishes

Windows attempts console-frequency beeps through the standard library and falls back to BEL. Linux and macOS use terminal BEL directly.

No WAV, MP3, external player, or additional audio package is required.

## Environment controls

Disable cues entirely:

    JERVIS_TERMINAL_CUES=0

Force cues when stdout is not detected as a normal TTY:

    JERVIS_FORCE_TERMINAL_CUES=1

By default Jervis avoids emitting cues into noninteractive stdout such as CI logs.

## Design rule

Cues should sound like terminal/workstation feedback, not application notification sounds. Keep them short and sparse.

## Related pages

- [Installer index](installer-index.md)
- [Installation Control Deck](installer-blue-ui.md)
