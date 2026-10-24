# Voice Engine 2.0

**State:** an 8.1 draft integration, not a complete Voice Engine 2.0 release.

The voice router now checks approved conversational offline intents before handing them to OpenClaw. Greetings, help, clock queries and diagnostics can use the local adaptive response composer, without a network or a model request. Existing stateful Jervis local actions retain precedence over these new responses.

The pre-existing voice engine continues to provide VAD, lazy Whisper STT, wake-word detection, identity/session enforcement, TTS, microphone selection and barge-in handling. The new composer **does not bypass speaker authentication**.

## Still to validate

- Real microphone/voice end-to-end testing across all three supported operating systems
- Wake-to-speech latency and p95 measurements compared with 8.0.1
- Interrupted playback and follow-up interactions with varied offline responses
- Model availability, audio-device unplug/reconnect and resource consumption on low-power devices
- Streaming speech output and model improvements, which are **not implemented** in this draft

[HyperCore](evolve-hypercore.md) · [Adaptive local dialogue](evolve-local-dialogue.md)
