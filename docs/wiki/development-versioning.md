# Development: Versioning

## Current policy

Jervis uses semantic-style `major.minor.patch` versions.

The current public line is **7.3.x**:

- **7.3.0** — public runtime-speed rebuild
- **7.3.1** — hardening/benchmarking/installer-polish maintenance release in development
- **7.4.x** — future feature line, intentionally separate from 7.3 maintenance

## Automated maintenance rule

Automated maintenance may increment **only the patch component** on the current major/minor line after validation.

Examples:

    7.3.0 -> 7.3.1   allowed
    7.3.1 -> 7.3.2   allowed
    7.3.x -> 7.4.0   not automatic
    7.x   -> 8.0.0   not automatic

Dependency updates must be adapted and tested before pins move. Do not bump the Jervis version just because an upstream package released a newer build.

## Version sources

The runtime/package version must remain aligned between:

- `src/jervis/version.py`
- `pyproject.toml`
- release documentation
- published release/tag

Installer completion UI must read the active runtime version rather than hard-code an old release string.

## Release documentation

Every release description must be derived from the actual code diff and document:

- Added
- Changed
- Removed
- Fixed
- compatibility notes where relevant

## Related pages

- [Development index](development-index.md)
- [Release Workflow](development-release-workflow.md)
- [Release Checklist](development-release-checklist.md)
