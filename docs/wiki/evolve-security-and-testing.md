# Jervis 8.1 — security and release gates

**This page distinguishes implementation from release readiness.** A successful build does not prove a safe release.

## Validation required

- All GitHub CI jobs pass on the **current 8.1 branch head**: Python 3.11/3.13, Linux/Windows/macOS, and five frozen native targets.
- Fresh install and in-place upgrade on Linux x64/ARM64, Windows x64 and macOS Intel/ARM64 are dogfooded where supported.
- Voice Engine 2.0 is tested with microphone capture, session authorization, STT, TTS, interruptions and repeat-aware local replies on real hardware.
- AES-GCM export/decrypt round trips, wrong passphrases, ciphertext tampering, symlink and overwrite races, archive-path traversal, backup size caps and restoration rollback are tested.
- Companion TLS fingerprint checking, pairing expiry, rate limits, LAN firewall guidance, token revocation and unauthorized access are validated. No LAN exposure by default.
- Plugin manifests are restricted to known declarative operations. Arbitrary code execution remains out of scope until a platform sandbox exists.
- Control Center stays bound to localhost with mandatory authentication, no privileged endpoints, no third-party assets, no leak of private state and no cross-origin access.
- Self-healing is read-only by default; any state change is explicitly confirmed, snapshot-backed and refuses symlink swaps.
- HyperCore latency targets are benchmarked **against 8.0.1 on identical hardware**, and no unmeasured speed improvements are advertised.

## Current release policy

Jervis 8.0.1 remains the published stable line. Do not bump the second version component, tag 8.1.0, merge PR #3, or publish new release assets until correctness, security and cross-platform acceptance gates are actually satisfied. **Draft** is a deliberate safety status, not a shipping stage.
