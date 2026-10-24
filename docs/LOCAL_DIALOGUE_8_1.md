# Jervis 8.1 — Local Dialogue Composer (draft)

The Jervis 8.1 offline-command prototype has a **fast, fully offline, auditable**
response renderer. It replaces repeated canned responses with safe sentence
grammars and bounded, context-sensitive novelty scoring. This is a dialogue
presentation engine, **not** a local language model, autonomous agent, or
evidence of consciousness.

## Architecture

1. **Strict intent gate** — \`resolve_offline()\` accepts only enumerated,
   side-effect-free command aliases. Unknown, destructive, and ambiguous
   instructions are rejected; the wording engine cannot authorize actions.
2. **Fact layer** — each recognized intent has an authoritative meaning.
   Time comes from the host's local clock at render time. Status and diagnostics
   replies direct the operator to \`jervis status\` and \`jervis doctor\` rather
   than inventing a system health report.
3. **Auditable grammar** — predefined, compatible opener/core/ending fragments
   give many coherent combinations per intent. Special frames distinguish
   morning/evening greetings and consecutive repeats.
4. **Adaptive scoring** — each candidate is weighted by tone preference,
   frame-use fatigue, and recent reuse of individual sentence fragments.
   Complete template IDs used in the last 24 turns are excluded until the
   available alternatives for that style are exhausted.
5. **Bounded anonymous memory** — at most 24 template identifiers, per-frame
   usage counts, the most recent *intent class*, and a repeat streak. No input
   utterances, output text, speaker embeddings, transcripts or account details
   enter the cache. Cache writes are best-effort, atomic, mode 0600 where
   supported, and reject symbolic-link target paths.
6. **Presentation only** — UI/voice clients can call \`reply_offline\` with the
   resolver's trusted \`OfflineIntent\`, but voice runtime integration remains
   part of future Voice Engine 2.0 work.

For an eligible frame, the relative selection weight is approximately

\`\`\`text
weight = frame_weight
       * tone_preference(style, repeat_streak)
       * 1 / (1 + 0.17 * sqrt(previous_frame_uses))
       * 0.78 ^ count(recently_reused_fragments)
\`\`\`

Sampling uses OS-backed randomness by default. Tests inject a seeded random
generator and a fixed clock for reproducibility. Fixed content must always
remain accurate: stylistic diversity must not rewrite facts or permissions.

## CLI examples

\`\`\`sh
jervis offline hello
jervis offline --style playful hello
jervis offline --style focused diagnostics
jervis offline "what time is it?"
jervis offline --json status
jervis offline --no-memory hello
\`\`\`

Styles: \`balanced\` (default), \`playful\`, and \`focused\`.
\`--no-memory\` avoids both reading and writing the anonymous variant cache.
\`--json\` returns structured metadata including intent and template identity.

## Test boundaries

Tests exercise multi-turn novelty, persistence across CLI invocations,
corrupt/oversize caches, symlink avoidance, tone choice, time correctness,
canonical fallback, strict non-action aliases and absence of invented health
claims. An isolated local development benchmark measured roughly 0.15 ms per
response render over 15,000 calls; this is **not** a cross-platform runtime
latency guarantee. Release acceptance still requires CI, integration with the
voice pipeline, and on-device performance measurements.

This feature lives on the Jervis 8.1 draft branch, not in stable 8.0.1.
