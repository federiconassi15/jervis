# Jervis Dogfood & Soak Plan

This checklist is the acceptance gate between Jervis 7.3 and the 7.4 feature cycle.

## Baseline capture

On the target machine, record:

    jervis --version
    jervis runtime-info
    jervis doctor
    jervis benchmark --json

Keep the JSON output from each build being compared. Do not compare “feels faster” without keeping the measured baseline too.

## Fresh install

Test from the public release path, not a repository checkout.

Validate:

- bootstrap starts on the target OS without Python/Node/Git preinstalled
- correct native binary is selected
- SHA-256 verification succeeds
- audio devices are detected
- OpenClaw is reused or provisioned
- owner/auth setup completes
- startup integration is installed
- first runtime start succeeds
- `jervis runtime-info` reports native acceleration on official native builds

## Voice loop

Exercise at least:

- 50 wake → command → response turns
- 20 follow-up turns without repeating the wake word
- 10 barge-ins while Jervis is speaking
- quiet, normal, and loud microphone input
- short and long commands
- fast/local commands and OpenClaw commands
- at least one deep-thinking OpenClaw request

Watch the live metrics exposed by `jervis benchmark`:

- `inference_ms`
- `brain_ms`
- `command_to_reply_ms`

## Identity / multi-user

- known owner
- second known user
- unknown speaker
- retry path
- passphrase escalation
- speaker learning
- active-user handoff
- ensure one user's memory/agent preference never leaks to another user

## Failure injection

Verify clean degradation for:

- Internet disconnected
- OpenClaw Gateway unavailable
- OpenClaw CLI unavailable
- microphone disappears
- output device disappears
- Android ADB disconnects mid-session
- very noisy input
- very quiet input
- state database already exists from an older release

## Reboot / long-running

- reboot host and verify startup
- leave Jervis idle for at least one hour, then wake it
- run a multi-hour soak session
- verify STT can unload/reload if configured
- verify presence timeout and proactive queue behavior
- confirm logs/state remain bounded

## Bug policy

During the 7.3.x hardening phase:

- fix correctness, security, startup, compatibility, and measured latency problems
- improve diagnostics/observability when it shortens debugging
- do not merge large “7.4” experience features into the stable hardening line

Any regression found here should include a reproducible test or benchmark case where practical.
