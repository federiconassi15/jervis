# Cross-platform Compatibility

Jervis 7.1 is one product across Linux, Windows, and macOS.

| Capability | Linux | Windows | macOS |
| --- | --- | --- | --- |
| Desktop audio | PortAudio host backend | WASAPI through PortAudio | CoreAudio through PortAudio |
| Android AudioSource | ADB TCP forward | ADB TCP forward | ADB TCP forward |
| Managed startup | systemd user service | Task Scheduler | launchd |
| Fallback TTS | espeak-ng / espeak | Windows SAPI | say |
| OpenClaw install | official shell installer | official PowerShell installer | official shell installer |
| Config/state paths | platformdirs | platformdirs | platformdirs |
| Control Deck | terminal | terminal | terminal |
| Trusted sessions | shared core | shared core | shared core |
| Permissions/state | shared core | shared core | shared core |

## Shared core

The following should not have OS-specific implementations unless absolutely necessary:

- trusted conversation sessions,
- speaker confidence logic,
- SQLite state,
- users and honorific preferences,
- permissions,
- skills,
- OpenClaw routing,
- dialogue/event semantics,
- update policy.

## Linux

Linux uses a systemd user service when available. Audio prerequisites may be installed using a supported package manager. The project must not assume Umbrel, a specific username, PulseAudio-only routing, or a particular home directory.

## Windows

Windows uses Task Scheduler for per-user automatic startup. Host audio is exposed through the Windows PortAudio/WASAPI backend. OpenClaw installation uses its official PowerShell installer.

Windows command quoting must be tested explicitly because scheduled-task and .cmd invocation rules differ from POSIX shells.

## macOS

macOS uses launchd for managed startup and CoreAudio through PortAudio for desktop devices. System TTS fallback uses the built-in say command.

## Android phone microphone

Android AudioSource is a portable optional microphone input. ADB forwards the app's abstract socket to localhost. Jervis consumes the stream itself instead of requiring the upstream Linux PulseAudio helper.

## Paths

Jervis asks platformdirs for config, state, cache, and log locations. Source code must not hard-code /home/umbrel, AppData usernames, or macOS home paths.

## Desktop versus Server

Desktop and Server remain independent from operating system. Linux can be a normal Desktop install, and Windows/macOS machines can run persistently where their host lifecycle allows it.
