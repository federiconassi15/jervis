# Getting Started: Uninstall & Reinstall

## Reinstall

    jervis reinstall

Reinstall removes Jervis-managed startup integration while preserving user state, creates recovery snapshots through the normal maintenance path, and launches the installer again.

## Uninstall but keep user state

    jervis uninstall

This removes the managed startup/service definition and creates a `pre-uninstall` snapshot.

## Purge Jervis state

    jervis uninstall --purge-data

Snapshots are preserved so the purge remains recoverable.

## Remove the native executable too

    jervis uninstall --purge-data --remove-binary

On Windows and other platforms where a running executable cannot delete itself immediately, removal is scheduled after the current process exits.

## Rollback

Use:

    jervis snapshot list
    jervis snapshot restore <snapshot-id>

The pre-uninstall recovery point contains Jervis mutable state and, when binary removal was requested, the native executable as well.

[Back to Getting Started](getting-started-index.md)
