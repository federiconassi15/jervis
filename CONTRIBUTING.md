# Contributing to Jervis

Thanks for considering a contribution.

Jervis is being built as a lightweight, local-first voice assistant with an emphasis on reliability, low resource usage, and clear failure recovery.

## Before you start

- Search existing issues before opening a new one.
- Keep changes focused. Large architectural changes should start as a discussion or feature request.
- Never include API keys, tokens, passwords, voiceprints, recordings, device serials, or private conversation logs.
- Do not copy machine-specific paths or credentials into examples.

## Development principles

Changes should generally preserve these goals:

1. **Low idle cost** — background work should be event-driven rather than busy-looped.
2. **Graceful degradation** — local wake/audio/control should continue when remote AI services fail.
3. **Bounded state** — queues, histories, caches, and databases should have sensible limits.
4. **Component repair first** — restart the smallest broken component before restarting the full runtime.
5. **Privacy by default** — avoid persisting raw audio or secrets unless explicitly required.
6. **Observable behavior** — important state transitions should be visible in logs or the Control Deck.

## Pull requests

A good pull request includes:

- what changed
- why it changed
- how it was tested
- any resource impact
- any migration or rollback considerations

If the change touches audio, identity, authentication, permissions, or persistence, describe the failure cases you tested.

## Commit messages

Short conventional-style messages are preferred, for example:

```text
feat: add trusted speaker sessions
fix: avoid duplicate wake acknowledgements
docs: explain OpenClaw integration
chore: bound dialogue history
```

## AI-assisted contributions

AI-assisted coding is welcome, but contributors are responsible for understanding, reviewing, testing, and licensing the code they submit.
