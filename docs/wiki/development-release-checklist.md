# Development: Release Checklist

## Jervis 8.0 maintenance gate

A patch release should change only the patch component of the current version, preserve existing state/configuration semantics, and have a changelog and matching `docs/releases/<version>.md` derived from its code diff.

## Before publishing

1. Confirm `src/jervis/version.py` and `pyproject.toml` agree.
2. Run focused regression tests for changes and review failures.
3. Verify Linux, Windows, and macOS CI, including native smoke tests and Rust acceleration in frozen builds.
4. Verify Linux x64/ARM64, Windows x64 and macOS Intel/Apple Silicon output asset names.
5. Review installer checksums, temporary-file handling, cleanup, rollback, update and start-up behavior.
6. Review risk to credentials, identity and session boundaries; never publish private state.
7. Preserve release note headings: **Added**, **Changed**, **Removed**, **Fixed**.
8. Trigger `Release` through a changed `.release-trigger` on `main` only when ready.
9. Confirm published GitHub tag, five native assets, source archives, all-platforms ZIP and `SHA256SUMS`.
10. Confirm `Sync GitHub Wiki` succeeded and current installation/versioning guidance is visible.

## Failure handling

An unverified release or missing checksum is a blocker, not an invitation to guess. Never automatically merge feature PRs, cross a major/minor version boundary, or ship an unverified dependency jump.

## Runtime reliability

Jervis must remain diagnosable when OpenClaw or a provider is down. Preserve `jervis doctor`, managed startup, snapshots and rollback, Desktop/Server consistency, and cross-platform permissions.

## Useful commands

```text
jervis doctor
jervis runtime-info
jervis acceptance-test
jervis snapshot list
jervis update-check
```

## Related pages

- [Development index](development-index.md)
- [Release Workflow](development-release-workflow.md)
- [Versioning](development-versioning.md)
- [Wiki Home](Home.md)
