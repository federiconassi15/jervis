# Getting Started: Updates

Jervis 8.0.x can install validated patch updates on the installed 8.0 line. Upgrading from an older 7.x line to 8.x is a separate compatibility decision, not an automatic patch update.

## Check

    jervis update-check

## Install an update

    jervis update

Before replacement Jervis:

1. creates a `pre-update-<version>` snapshot,
2. includes the current native executable in that snapshot,
3. downloads the platform-specific release asset,
4. downloads `SHA256SUMS`,
5. verifies the downloaded binary,
6. smoke-tests the staged binary with `--version` and `runtime-info`,
7. replaces the current executable only after those checks pass.

On Windows the final executable swap happens after the current process exits. The updater keeps the prior executable and restores it automatically if the replacement cannot start.

## Roll back the latest update

    jervis update --rollback

Or choose a specific update snapshot:

    jervis update --rollback <snapshot-id>

You can inspect all recovery points with:

    jervis snapshot list

## Source installs

Automatic binary replacement targets official frozen Jervis releases. Source/development installs should reinstall from the matching wheel/source release rather than overwriting the active Python environment.

## Version boundary

Automated maintenance stays on the current major/minor line. An 8.0.x build can move to another validated 8.0.x patch; it does not automatically become 8.1 or 9.x. Earlier 7.x installations stay on their own release line unless deliberately migrated.

[Back to Getting Started](getting-started-index.md)
