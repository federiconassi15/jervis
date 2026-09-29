# Architecture

Jervis is designed around one rule: **the local voice shell should remain useful even when the AI brain is unavailable**.

## High-level flow

```text
Audio input
   │
   ├─ Acoustic echo cancellation
   ├─ Voice activity detection
   └─ Wake-word detection
          │
          ▼
  Conversation session
          │
          ├─ Speaker identity
          ├─ Permissions
          └─ Context
          │
          ▼
      Intent router
     /      |       \
local    skill     brain
command             │
                    ▼
               OpenClaw / agent
                    │
                    ▼
             Response manager
                    │
                    ▼
             Interruptible TTS
```

## Design constraints

### Low-resource first

The runtime should avoid unnecessary daemons, repeated subprocess launches, unbounded caches, and hot polling loops. Expensive speech models should be loaded lazily when possible.

### Local shell independence

Wake detection, local commands, audio output, identity state, and diagnostics should not crash because an external model or provider is offline.

### Event-driven state

Presence, authentication, dialogue, and health state should emit events instead of relying on constant high-frequency polling.

### Bounded persistence

SQLite-backed histories and metrics should be indexed, bounded, and periodically pruned.

### Component repair

A failure in one audio bridge, agent, or provider should trigger the smallest possible repair action before a whole-runtime restart is attempted.

## Major subsystems

- **Audio** — sources, sinks, AEC, gain, VAD, signal health.
- **Wake** — low-cost always-on keyword detection.
- **Speech** — transcription, TTS, barge-in, follow-ups.
- **Identity** — speaker profiles, trusted sessions, confidence scoring.
- **Permissions** — action-level authorization.
- **Router** — chooses local, skill, MCP/agent, or OpenClaw execution.
- **State** — conversations, events, metrics, user preferences.
- **Control Deck** — operator-facing terminal interface.
- **Resilience** — health checks and targeted repair.
