# Audio: Acoustic echo cancellation

## Status in Jervis 7.1

Jervis 7.1 **does not claim a live acoustic echo-cancellation pipeline**. The
configuration key exists for forward compatibility, but its public default is
off.

The 7.1 runtime instead avoids mixing Jervis's own speech into the next command
as much as possible by:

- playing Jervis speech through the explicitly selected output device;
- pausing command capture while Jervis is speaking;
- flushing queued microphone frames immediately after speech playback;
- beginning the next capture from fresh microphone data.

This is deliberately documented as playback/capture separation, not AEC.

## Why the distinction matters

True AEC needs a synchronized far-end reference of the audio being played,
along with the microphone stream. Merely lowering a microphone threshold or
discarding a few frames is not acoustic echo cancellation.

A future Jervis release may add a cross-platform WebRTC-style audio processor,
but it must be wired to both streams and validated on Linux, Windows, and
macOS before the AEC setting is enabled by default.

## Troubleshooting self-echo

If Jervis hears its own voice:

1. Lower the physical speaker level or increase microphone distance.
2. Confirm the configured output device is the device actually playing Jervis.
3. Confirm the microphone queue is being flushed after speech.
4. Prefer headphones while diagnosing.
5. Do not compensate by aggressively raising speaker-recognition thresholds.

## Related pages

- [Audio index](audio-index.md)
- [Barge-in](audio-barge-in.md)
- [Desktop input](audio-desktop-input.md)
- [Desktop output](audio-desktop-output.md)
