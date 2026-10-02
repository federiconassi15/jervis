# Operations: Status

Jervis 7.3.5 exposes a compact health dashboard:

    jervis status

Machine-readable form:

    jervis status --json

The report includes:

- Jervis version
- managed service/startup health
- OpenClaw health
- active acceleration backend
- recent command-to-reply median when benchmark history exists
- snapshot count and latest snapshot
- previous unclean-runtime/crash state

Example:

    ┌─ JERVIS 7.3.5 // SYSTEM STATUS ──────────────────┐
    │ CORE       ● ONLINE
    │ SERVICE    ● ACTIVE
    │ OPENCLAW   ● ONLINE
    │ ACCEL      ● RUST
    │ LATENCY    412 ms median
    │ SNAPSHOTS  4
    │ RECOVERY   ● clean
    └───────────────────────────────────────────────────┘

The Control Deck also includes a **RECOVERY** tab with the same recovery-oriented view.

## Benchmark history

    jervis benchmark-history

This shows recent command latency and whether each comparable run was faster or slower than the previous recorded run.

[Back to Operations](operations-index.md)
