# Operations: Repair Center

Open the terminal Repair Center:

    jervis repair-center

Or use the Control Deck **RECOVERY** tab.

## Repair components

    jervis repair audio
    jervis repair openclaw
    jervis repair startup
    jervis repair database
    jervis repair models
    jervis repair permissions
    jervis repair all

Each repair creates a `pre-repair-<component>` snapshot before changing Jervis-owned state.

The database repair performs an integrity check and optimization. Startup repair recreates the managed systemd/Task Scheduler/launchd integration from current config. Model repair verifies the local speaker model. Permissions repair normalizes Jervis config/data permissions where the platform supports POSIX modes.

## Rollback a repair

    jervis snapshot list
    jervis snapshot restore <snapshot-id>

[Back to Operations](operations-index.md)
