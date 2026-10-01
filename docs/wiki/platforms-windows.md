# Platforms: Windows

## Runtime model

Windows uses the same Jervis core, config schema, trusted-session logic,
OpenClaw integration, and Control Deck as Linux and macOS.

Desktop audio is exposed through PortAudio's Windows host APIs, normally
WASAPI. Android AudioSource can also be selected through ADB.

## Desktop startup

Jervis registers a per-user Task Scheduler task that starts when that user
logs in. It stays in the interactive user session so Windows audio devices
remain available.

## Server mode

Jervis server mode on Windows means **persistent always-on behavior for the
logged-in Jervis user**, not a Session-0 SYSTEM service.

This is intentional. A SYSTEM startup task can run before login, but Windows
audio capture/playback belongs to interactive user sessions. Running the voice
assistant as SYSTEM would make microphone/speaker parity unreliable.

Server mode therefore keeps:

- the same interactive audio access as Desktop mode;
- unlimited task execution time;
- automatic restart settings;
- automatic startup when the configured user logs in.

For a truly headless-before-login Windows service, use a future service backend
that explicitly bridges the audio session; Jervis 7.1 does not pretend this is
already solved.

## Diagnostics

Run `jervis doctor`, inspect Task Scheduler's **Jervis Voice Assistant**
task, and verify the selected WASAPI devices are visible to the logged-in user.

## Related pages

- [Platforms index](platforms-index.md)
- [Desktop versus server](platforms-desktop-vs-server.md)
- [Windows task scheduler](platforms-task-scheduler.md)
