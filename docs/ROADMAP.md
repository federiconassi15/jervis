# Roadmap

This roadmap describes direction, not guaranteed release dates.

## Jervis 7.1 — Voice reliability

Primary goal: make normal conversation feel continuous instead of repeatedly re-authenticating the same person.

Planned work:

- **Trusted conversation sessions** — successful identity persists for a sensible session window and refreshes during active conversation.
- **Longer speaker samples** — identify from natural follow-up speech rather than only the short wake word.
- **Confidence bands** — strong match, session-assisted match, uncertain/retry, and authentication-required states.
- **Retry before password** — one natural retry before requiring explicit authentication.
- **Continuous voice learning** — accept only high-confidence, clean samples into a speaker profile.
- **Conversation lock-on** — follow-up turns remain associated with the current speaker unless another speaker is confidently detected.
- **"Boss?" acknowledgement** — short wake response while the next utterance is captured.
- **Sensitive-action escalation** — ordinary conversation can use trusted sessions while privileged actions may require stronger confidence or explicit authentication.

## Jervis 7.x

- multi-user preferences and memory
- permissions and roles
- presence awareness
- skills
- MCP / agent hub
- proactive notifications and quiet hours
- richer event timeline
- audio-quality monitoring
- component-level self-repair
- expanded Control Deck

## Public installer

A generic installer will be published only after machine-specific assumptions have been removed and install/rollback behavior has been tested on a clean target.
