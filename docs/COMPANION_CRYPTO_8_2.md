# Jervis 8.2 authenticated companion cryptographic channel

This module is experimental, **not deployed and not wired into remote chat**.
It provides a portable protocol contract for the native Android client and
the local Jervis host to implement together.

1. Host and phone each possess a long-lived P-256 signing identity. Public
   identities must be pinned following owner-confirmed physical QR pairing.
   The host must reject unpaired phone identities. The phone must reject
   hosts whose identity differs from its pinned QR record.
2. Each session generates fresh ephemeral P-256 ECDH keys and 128-bit session ID.
3. Phone signs its ephemeral public key, device ID, instance ID and session ID;
   host verifies against the paired phone identity.
4. Host signs both ephemerals and identifiers; phone verifies against its
   pinned host identity.
5. Both derive directional AES-256-GCM keys and nonce prefixes using
   HKDF-SHA256 over the bound transcript. Strict monotonically increasing
   sequences and authenticated direction/session metadata prevent replay and
   reflection.
6. Keys are ephemeral process memory only; establish a new handshake on
   reconnect. Do not reuse encryption keys after a client restart.

The relay is untrusted for confidentiality and may inspect routing metadata,
drop, delay or replay frames. Endpoint authentication and monotonic replay
tracking protect message integrity, but the relay cannot be relied on to
guarantee availability. The host must still enforce per-device capabilities,
authentication and explicit approval for privileged actions.

Android's Kotlin implementation, key-store persistence, public-key pinning,
device revocation, cross-language known-answer tests, network integration,
message delivery/ack protocol and a full security review are **still required**.
No private signing key, shared secret or PII belongs in source, logs or Git.

The native Android Kotlin implementation now includes the same P-256/HKDF/AES-GCM protocol with a deterministic cross-language test vector. This does not yet connect Android networking, key-store persistence or pairing UX.

Transport adapters now wrap authenticated channel envelopes in the relay's opaque v1 five-field format; unpacking checks the outer and inner sequence IDs, while decryption still authenticates everything. Kotlin tests use the official JVM org.json test dependency; Android already includes org.json at runtime.
