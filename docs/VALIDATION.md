# Jervis 7.1 Validation Gates

This file describes the validation contract for the current release-candidate branch. It intentionally does **not** hard-code an old commit SHA, run number, wiki-page count, or installer format.

## Automated CI

Every push to `main` or `build/**` runs the latest branch head through:

- Ubuntu, Windows, and macOS on Python 3.11 and 3.13 for source/developer compatibility
- compilation of source, tests, and scripts
- repository UTF-8 / syntax / merge-marker / local-link verification
- smoke tests
- unit tests
- Ruff correctness checks
- wheel and source-distribution builds
- native bootstrap syntax checks
- self-contained native binary builds and smoke verification for:
  - Linux x64
  - Linux ARM64
  - Windows x64
  - macOS Intel
  - macOS Apple Silicon

CI uses branch-level concurrency so stale runs are cancelled when a newer commit supersedes them.

## Fresh-machine installer contract

The public install path must not require a preinstalled Python, Node.js, npm, pip, Git, or virtual environment.

- `install.sh` detects Linux/macOS architecture, obtains the matching native binary, verifies `SHA256SUMS`, and launches it.
- `install.ps1` performs the equivalent flow on Windows.
- the native binary carries the Jervis Python runtime internally.
- Linux host libraries or command-line tools that Jervis actually needs are provisioned through the host package manager inside the setup flow.
- installer navigation is mouse + arrow-key driven; raw pre-TUI yes/no prompts are forbidden.

## Repository hygiene gates

The repository verifier rejects:

- invalid UTF-8
- unexpected control bytes
- unresolved merge-conflict markers
- invalid Python/JSON/TOML/YAML syntax
- broken local Markdown links
- version mismatches
- missing native bootstrap scripts
- reintroduction of the obsolete Python bootstrap entrypoints

## Manual release gate

Before merging the RC into `main`, review:

1. installer rollback and fresh-machine bootstrap
2. identity/authentication and permission boundaries
3. audio input/output and Android ADB input
4. OpenClaw discovery, install, auth, agent selection, and degradation
5. per-user state, memory, presence, and speaker learning
6. local/skill/OpenClaw routing
7. proactive quiet-hours behavior and component repair
8. Control Deck panels and timeline observability
9. startup adapters on Linux, Windows, and macOS

A release is not considered ready merely because one historical workflow run passed.
