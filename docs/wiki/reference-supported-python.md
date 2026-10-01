# Reference: Supported Python

Python is an implementation and development runtime for Jervis, but it is **not a public fresh-machine prerequisite**.

## End users

Stable releases use self-contained native binaries with the required Python runtime bundled inside. Users should start from `install.sh`, `install.ps1`, or the matching native release asset.

## Source developers

The source tree supports Python 3.11 and 3.13 in CI. The package metadata requires Python 3.11 or newer.

Typical development setup:

    python -m pip install -e ".[dev]"

The Python compatibility matrix exists to keep source development and native release builds healthy; it must not leak back into the public installer contract.

See [Reference: Release Assets](reference-release-assets.md) and [Getting Started: Installation](getting-started-installation.md).
