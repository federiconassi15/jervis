# Development: Release Workflow

## Current release line

**Jervis 8.0.x** is the current maintenance line. The 8.0.1 patch contains POSIX bootstrap cleanup and private-directory hardening; it does not bundle draft 8.1 functionality.

## Jervis 8.1 release gate

The Evolve draft must pass [security and release acceptance](evolve-security-and-testing.md) before its version is changed or a stable 8.1 tag is created. The current CI workflow is necessary but is not sufficient to prove hardware voice performance or LAN pairing security.

## Release source of truth

```text
src/jervis/version.py
pyproject.toml
CHANGELOG.md
docs/releases/<version>.md
```

The release workflow uses the matching release document for the GitHub release body and retains Added / Changed / Removed / Fixed sections.

## Publishing

The `Release` GitHub Actions workflow runs on changes to `.release-trigger` on `main` or via manual dispatch. It verifies the version, builds source and native packages, verifies five native platform assets, bundles an all-platforms ZIP and SHA256SUMS, then publishes a stable tag and release.

Publishing is complete only when the workflow succeeds and the new tag, assets and checksums appear on GitHub. Green CI alone does not publish a release.

## Native matrix

- Linux x64/ARM64
- Windows x64
- macOS Intel/Apple Silicon

Native verification checks that the Rust/PyO3 acceleration backend is present.

## Wiki publication

`docs/wiki` is the source for the GitHub Wiki. `Sync GitHub Wiki` runs on main after wiki-source changes, normalizes links and pushes the resulting pages into the separate wiki repository. The wiki must first have been initialized. Historical 7.x reference pages are labeled, not silently rewritten to claim they describe Jervis 8.

## Security / release hygiene

Never publish credentials, private paths, IDs, logs, voiceprints or device-specific state. Verify release assets and checksums before announcing completion.

## Related pages

- [Development index](development-index.md)
- [Versioning](development-versioning.md)
- [Release Checklist](development-release-checklist.md)
- [Wiki Home](Home.md)
