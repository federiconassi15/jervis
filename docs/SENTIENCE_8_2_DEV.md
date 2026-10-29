# Jervis 8.2 SENTIENCE — development foundations

**Status: experimental branch; not released or approved for deployment.**
Stable Jervis and the draft 8.1 PR are not changed by this branch.

## Implemented in the first increment

- Private JSONL event journal with bounded rotation, canonical event messages,
  stable codes, correlation identifiers and numeric-only safe metrics.
- Read-only 'jervis logs' CLI for filtered human-readable output or structured JSON.
- Runtime start/stop/crash lifecycle event instrumentation.
- Standalone default-deny capability policy with identity, role, explicit scopes,
  expiry, device bindings and fresh-auth gates.

This policy is not yet wired into the existing 8.1 skill and companion execution
paths. Consequently **do not expose new write operations** through the GUI,
remote device endpoints, plugins, agents or automations yet. Status only remains
the safe 8.1 companion behavior.

## Not implemented or verified

Full event bus, memory/knowledge expansion, streaming voice, custom wake-word
training, screenshot capture, persistent missions, Dev Mode tooling, workflow
builder, plugin sandbox, Control Center 2.0, Android client and Cloudflare relay.
No physical microphone, installer, power-cut, Android or OS-specific acceptance
has been performed for 8.2.

## Existing 8.1 prerequisite

Encrypted backup export still creates a plaintext staged snapshot on disk.
Encrypted restore import still needs exclusive destination publication and
concurrency-safe cleanup. These must be resolved and tested before remote
write-capable features or a release. Existing local snapshots are not encrypted.

## Review gates

- Privacy: reject all unregistered messages, arbitrary strings and sensitive
  metadata from the default operational journal.
- Compatibility: Python 3.11/3.13 on Linux, Windows and macOS; native packages.
- Security: authorization is deny by default, per device and per resource.
- Performance: bounded storage, no logging from the hot audio sample callback.
- Release: verify CI and physical-device acceptance on exact final artifacts;
  never advertise unfinished features as shipped.
