# Encrypted Backups — password-protected exports

**State:** AES-256-GCM encrypted archive export and authenticated restore have been implemented in the 8.1 draft.

```sh
jervis backup encrypt /safe/place/jervis.jenc
jervis backup restore-encrypted /safe/place/jervis.jenc
```

The CLI prompts locally for a backup passphrase (at least 12 characters; twice when creating). **Never put passwords in shell arguments, scripts, logs or shared screenshots.** Archive encryption uses AES-256-GCM with random salt/nonce and an scrypt-derived key; metadata is authenticated before restoration. Wrong passwords and modified ciphertext fail closed, leaving no decrypted output.

The encrypted file is published without overwriting an existing destination. Decryption uses private temporary files, verifies the authentication tag, validates archive paths and metadata, and **only then** calls the existing snapshot-backed restore engine. Export size is limited to 2 GiB.

## Crucial limitation

Only the **exported archive** is encrypted. Existing Jervis state, historical recovery snapshots and pre-restore guard snapshots remain plaintext on the local machine; their filesystem permissions must be protected. The restore engine is not yet a full cross-platform atomic transaction with power-loss recovery. Independently back up important state before restoring.

[Recovery](evolve-self-healing.md) · [Security gates](evolve-security-and-testing.md)


## Import concurrency hardening (8.1 draft)

The imported snapshot path is now created exclusively, so a competing
restorer cannot have its archive overwritten by a check-then-copy race.
Cleanup compares the original file's identity and never intentionally
removes a different replacement archive. This does **not** make all
same-user hostile filesystem races or power-loss rollback atomic.
The plaintext staging/export interruption issue remains an open release
blocker and must be verified separately on physical filesystems.


## Streaming export hardening (8.1 draft)

Encrypted export streams current configuration and state directly into the
AES-GCM-encrypted destination. There is no intermediate plaintext archive on
disk; SQLite's consistent backup is generated in bounded memory (128 MiB limit).
If a database is too large for that memory ceiling, export fails explicitly
rather than silently spilling sensitive backup data onto disk. Existing state,
ordinary recovery snapshots and guard snapshots are still unencrypted.
Abrupt termination, filesystem faults and multi-process scenarios require
independent real-device acceptance before release.
