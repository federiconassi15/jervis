# Development: Versioning

## Current policy

Jervis uses `major.minor.patch` versions. The current stable maintenance line is **8.0.x**.

- **8.0.0** — plain terminal home and installer; legacy Control Deck is opt-in
- **8.0.1** — POSIX bootstrap temporary-directory hardening and cleanup
- **8.1.x** — separate feature line, excluded from automatic 8.0 maintenance

## Automated maintenance

Only advance the **patch** component of the currently released major/minor line after verification.

```text
8.0.0 -> 8.0.1    patch maintenance
8.0.1 -> 8.0.2    patch maintenance
8.0.x -> 8.1.0    not automatic
8.x   -> 9.0.0    not automatic
```

Dependency changes must be adapted and tested before updating pins.

## Version sources

Keep these aligned:

- `src/jervis/version.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `docs/releases/<version>.md`
- published GitHub tag and release

## Release documentation

Every release description must reflect the actual code diff and include Added / Changed / Removed / Fixed sections, with compatibility and validation notes.

## Related pages

- [Development index](development-index.md)
- [Release Workflow](development-release-workflow.md)
- [Release Checklist](development-release-checklist.md)
