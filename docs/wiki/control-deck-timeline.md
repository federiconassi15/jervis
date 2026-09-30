# Control Deck: Timeline

## Purpose

This page covers **Timeline** for the **Control Deck** subsystem in Jervis 7.1. The goal is to keep the feature understandable, inspectable, and portable across Windows, macOS, and Linux without splitting Jervis into separate products.

## Runtime relationship

Jervis separates the always-on local shell from the OpenClaw brain. Wake detection, audio capture, session identity, local state, permissions, and diagnostics should continue operating when OpenClaw or an external model provider is unavailable. Timeline must respect that failure boundary.

The active conversation model favors continuity: once a user is strongly identified or explicitly authenticated, Jervis maintains a trusted session and refreshes it through natural follow-up turns. A single uncertain sample should produce a retry or session-assisted result, not an immediate password loop.

## Deployment behavior

Desktop mode integrates with the current user's normal audio devices and login session. Server mode uses the same feature set but prioritizes persistence, explicit hardware selection, and remote diagnostics. Platform adapters translate Jervis lifecycle operations into systemd, Task Scheduler, or launchd.

## Configuration

Configuration is validated before activation and written atomically. Avoid embedding OS paths, usernames, IP addresses, device serials, provider keys, or personal identity values into source code. Machine-specific choices belong in local configuration or state.

## Operational guidance

For Timeline, prefer observable state over hidden behavior. Important transitions should emit events into the timeline, and errors should be actionable. Long-running background work should be event-driven or rate-limited so a low-resource server is not punished by idle polling.

## Security rules

- Treat microphone data and speaker embeddings as sensitive local data.
- Do not log spoken passwords or TUI authentication secrets.
- Enforce permissions at the action boundary.
- Do not assume a recognized voice is sufficient for destructive or privileged operations.
- Keep third-party skills and agents isolated from secrets they do not need.

## Cross-platform behavior

The shared Python core owns semantics. OS adapters own startup and host integration only. Tests should prove that platform-specific code can be imported safely on the other operating systems without executing unavailable host commands.

## Troubleshooting flow

1. Run `jervis doctor`.
2. Check the Control Deck timeline.
3. Confirm the active config path and selected devices.
4. Check service state on the current OS.
5. If OpenClaw is involved, run `openclaw doctor`.
6. Reproduce with sanitized logs before changing thresholds or reinstalling.

## Development checklist

- Normal path tested.
- Failure path tested.
- No secret leakage.
- Bounded storage and queues.
- No unnecessary busy loop.
- Works with missing optional provider.
- Rollback path still valid.
- Documentation updated when user-facing behavior changes.

## Related pages

- [Control Deck index](control-deck-index.md)
- [Wiki Home](Home.md)
- [Previous](control-deck-permissions.md)
- [Next](control-deck-logs.md)
