# Platforms: macOS

## Runtime model

macOS uses the same Jervis core, config schema, trusted-session logic,
OpenClaw integration, and Control Deck as Linux and Windows.

Desktop audio uses CoreAudio through PortAudio. Android AudioSource can also be
selected through ADB.

## Startup

Jervis 7.1 uses a per-user launchd **LaunchAgent**. This keeps Jervis inside
the logged-in user's GUI/CoreAudio session, where microphone privacy
permissions and normal audio devices are available.

## Server mode

Server mode on macOS means a persistent background LaunchAgent for the Jervis
user. It deliberately does **not** install a LaunchDaemon in the system domain.

That choice avoids pretending a system LaunchDaemon has the same CoreAudio and
TCC microphone access as the user session. The voice assistant still starts
automatically for the configured user and is kept alive by launchd.

A future version can add a different privileged/headless architecture if it
can preserve microphone permissions and audio parity correctly.

## Privacy permissions

The first microphone use may trigger macOS privacy consent. Grant microphone
access to the terminal/runtime process Jervis is using. If capture is silent,
check **System Settings → Privacy & Security → Microphone** before changing
recognition thresholds.

## Diagnostics

Run `jervis doctor`, inspect the LaunchAgent with launchctl, and confirm the
selected CoreAudio devices are visible in the logged-in user session.

## Related pages

- [Platforms index](platforms-index.md)
- [Desktop versus server](platforms-desktop-vs-server.md)
- [launchd](platforms-launchd.md)
