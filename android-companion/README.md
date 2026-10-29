# Jervis Companion — Terminal Blue (Android development)

This folder contains a native Kotlin / Jetpack Compose Android project with
accessible blue terminal-style navigation and local disconnected-state screens:
Chat, Missions, System, Logs and Settings.

**Important:** This is the visual foundation, **not a working remote assistant**.
It does not contain real host pairing, Cloudflare credentials, network transport,
remote commands, voice capture, notifications or end-to-end encryption. No
network request is made and no API key is shipped in the APK. The Send button
is deliberately disabled until the real cryptographic transport is validated.
Do not advertise this as a completed Jervis Companion release.

Development tooling: Android Gradle Plugin 9.4.1, Gradle 9.6, Kotlin Compose
compiler plugin 2.4.21, stable Compose BOM 2026.09.00, compileSdk 37.0.
Android Studio/SDK and a real physical Android test device are required
for acceptance. Build: 'gradle :app:assembleDebug' from this directory.

Next mandatory protocol milestones:
1. Outbound-only TLS WebSocket relay with a verified, authenticated host/device
   handshake (no port forwarding).
2. Per-device scoped credentials, revocation, and host-bound pairing.
3. Audited message-level encryption and authenticated replay-protected envelopes.
4. Host-side capability checks and remote mission approval.
5. FCM notification integration without plaintext sensitive payloads.
6. End-to-end Android tests on Wi-Fi/mobile-data transitions, host offline,
   background restriction and certificate/identity mismatch.

The optional RelayTransport class now supports an outbound-only authenticated WSS connection. It is deliberately **not invoked** from the app UI until the relay deployment, host-bound pairing, encrypted identities, revocation and Android lifecycle integration have passed acceptance. OkHttp 5.5.1 is used for TLS WebSocket transport. No token is bundled with the APK.
