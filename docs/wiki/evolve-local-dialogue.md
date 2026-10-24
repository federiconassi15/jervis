# Adaptive Local Dialogue

**State:** implemented in the 8.1 draft's CLI and recognized voice fast path.

Rather than randomly swapping individual words, Jervis assembles coherent responses from intent-specific sentence frames. Frames are weighted by response tone, recent frame usage, recent fragment repetition, daypart, and consecutive same-intent turns. The previous 24 template IDs are avoided while unused alternatives exist.

```sh
jervis offline hello
jervis offline --style playful hello
jervis offline --style focused diagnostics
jervis offline --no-memory hello
jervis offline --json "what time is it?"
```

Three tones are available: `balanced`, `focused`, `playful`. The current algorithm handles greeting, help, time, status and diagnostics intents.

## Privacy and correctness

Saved variant history contains only anonymous template identifiers, usage counters, and the last **intent class**; it does not store your phrase, transcript, voice model or rendered response. `--no-memory` disables reading and writing it. For real system health, the response points to `jervis status` or `jervis doctor`; it never fabricates a healthy state.

See [design notes](https://github.com/federiconassi15/jervis/blob/feature/jervis-8.1-integrated/docs/LOCAL_DIALOGUE_8_1.md).
