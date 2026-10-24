# Self-Healing — bounded recovery checks

**State:** read-only local diagnostics and consented POSIX permissions repair implemented. Autonomous repair orchestration is not yet released.

```sh
jervis self-heal
jervis self-heal plan --json
jervis self-heal apply permissions
```

The planner checks configuration syntax/shape, SQLite integrity in read-only mode, recovery snapshot validity, and local private-file permissions. Missing installation is a warning, not a demand to reinstall.

Permission repair requires terminal confirmation (or an explicit `--yes` operator choice), writes a pre-repair snapshot, refuses symlinks, and restricts private files to owner-only modes on POSIX. It does not reinstall OpenClaw, restart services, delete data, alter Windows ACLs or roll back to another snapshot on its own.

Always inspect the plan and keep an independent backup. See [release and security gates](evolve-security-and-testing.md).
