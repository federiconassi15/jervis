# HyperCore — performance fast path

**State:** local fast routing and latency measurement implemented in the 8.1 draft. No claims of system-wide speedup have been validated.

HyperCore avoids network and model invocation when a fully enumerated offline command has been recognized. The speech router uses the existing Jervis local route before attempting any OpenClaw/skill route. Adaptive local wording uses bounded in-memory fatigue and recent-template history, so no transcript is cached.

## Measure

```sh
jervis hypercore --iterations 250
jervis hypercore --iterations 1000 --json
jervis benchmark --iterations 100 --json
```

The HyperCore probe measures local intent resolution and text composition only; it **does not** include microphone capture, STT, speaker authentication, TTS, or cloud/OpenClaw round trips. The existing Jervis benchmark tracks live command latency, inference and audio processing separately.

## Design limits

Only a strict allowlist uses the fastest offline route. Ambiguous requests still go through normal routing and permission checks. Latency windows retain at most 256 timings, not user text. A speed improvement must be measured on equivalent hardware and workloads before release notes claim a percentage.

[Adaptive local dialogue](evolve-local-dialogue.md) · [Voice Engine 2.0](evolve-voice-engine.md)
