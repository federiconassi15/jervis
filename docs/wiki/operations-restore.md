# Operations: Restore & Rollback

Jervis 7.3.5 treats rollback as a first-class maintenance operation.

## List recovery points

    jervis snapshot list

## Restore a snapshot

    jervis snapshot restore <snapshot-id>

Before applying a restore, Jervis creates a `pre-rollback-guard` snapshot unless an internal recovery path explicitly disables the extra guard.

Managed startup is stopped during state replacement and restarted afterward when it was previously installed.

## What is restored

Snapshots restore Jervis-owned mutable configuration and data. Live SQLite state is captured with SQLite's backup API.

Re-downloadable model/tool caches are preserved in place instead of being rolled backward with user state.

## Binary rollback

Snapshots created for native updates can include the executable. Windows schedules binary replacement after process exit; POSIX native builds can atomically replace the executable while it is running.

## Backup restore

    jervis backup restore <file>

Backup restore first creates a separate pre-restore snapshot.

[Back to Operations](operations-index.md)
