# Jervis Neural Voice 3.0 + Wake Word Studio — safe foundations

Experimental modules. **Not yet a streaming audio engine.**

- \`speech.turns.TurnManager\` owns strictly sequential wake/listen/think/speak
  phases and invalidates stale callbacks after barge-in, cancellation or stop.
  It never copies a previous speaker's authentication into a new turn.
- \`SpeechChunkBuffer\` splits bounded model text for future low-latency TTS,
  but incomplete output cannot trigger privileged commands.
- \`wake_studio.WakeStudio\` saves private version-1 PocketSphinx phrase
  configurations and always requires a default fallback.

Still required: integration with the existing audio runtime and identity
manager; sample-by-sample AEC, STT partials, streaming TTS, real microphone
measurements, configurable wake detector threshold, custom model training
where supported, and Windows/Linux/macOS device acceptance. Do not claim
full-duplex speech or custom wake model training is operational yet.
