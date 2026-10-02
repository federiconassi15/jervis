# Getting Started: Updates

Jervis 7.3.5 can update official native builds on the current 7.3 patch line without skipping directly to a new minor/major release.

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

Automated maintenance stays on the current major/minor line. A 7.3.x build can move to another validated 7.3.x patch; it does not automatically become 7.4 or 8.x.

[Back to Getting Started](getting-started-index.md)
