# Jervis 8.2 Knowledge Vault — opt-in local retrieval

Experimental source-only feature. Index one explicitly approved directory into
a local SQLite FTS5 database; no network service, auto-indexing, embeddings or
remote retrieval is provided yet. Supports .txt/.md/.rst/.py/.json/.csv (UTF-8)
and incrementally refreshes changed or removed files. Indexing is bounded to
2000 files, 1 MiB each, 128 MiB per sweep. Symlinks are skipped or rejected.

The index stores plaintext document contents. It must remain inside Jervis
private data storage and under the user's access policy; no provider may receive
retrieved text without an approved route. Files remain untrusted input, not
assistant instructions. Platform ACLs, privacy deletion and full backup/migration
integration are still outstanding before general deployment.
