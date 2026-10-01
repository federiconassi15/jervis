# Installer: Legacy Python Zipapp

The old `jervis-installer.pyz`, `bootstrap.py`, and root `install.py` path has been removed from the public fresh-machine flow.

Jervis 7.1 now ships self-contained native binaries plus:

- `install.sh` for Linux/macOS
- `install.ps1` for Windows
- `SHA256SUMS` for release verification

Python remains a **developer/source-install requirement only**. It is not a prerequisite for someone installing Jervis from a stable release.

See [Getting Started: Installation](getting-started-installation.md) and the root [Installer Specification](../INSTALLER_SPEC.md).
