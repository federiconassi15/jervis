# Getting Started: Backups & Snapshots

Jervis 7.3.5 uses one recovery format for automatic snapshots and user-created backups.

## Manual snapshot

    jervis snapshot create "before changing audio"
    jervis snapshot list
    jervis snapshot restore <snapshot-id>

Snapshots include mutable Jervis state such as configuration, SQLite state, memory and user skills. Large re-downloadable model/tool caches are not duplicated into every snapshot and are preserved during restore.

A restore creates a guard snapshot first so the rollback itself can be undone.

## Export a backup

    jervis backup create ~/jervis-backup.tar.gz

Restore it later:

    jervis backup restore ~/jervis-backup.tar.gz

Backup restore creates a pre-restore snapshot before applying the imported state.

## Automatic snapshots

7.3.5 automatically creates recovery points before update, install/reconfiguration, repair, migration, real config edits, restore and uninstall operations.

Rapid config edits are coalesced so changing a slider repeatedly does not create dozens of nearly identical recovery points.

## Live database safety

Jervis uses SQLite's backup API for the live state database instead of blindly copying a possibly active WAL database.

[Back to Getting Started](getting-started-index.md)
