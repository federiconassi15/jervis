# Security Policy

## Supported versions

Jervis has not reached its first stable public release yet. Until then, security fixes are applied to the current development line.

## Reporting a vulnerability

Please **do not publish secrets, authentication material, voiceprints, or exploit details in a public issue**.

For a suspected vulnerability:

1. Use GitHub's private vulnerability reporting feature if it is enabled for this repository.
2. Otherwise, open a minimal public issue stating that you have a security concern **without including sensitive details**, so a private channel can be arranged.

## Sensitive data

Jervis may interact with:

- microphone audio
- speaker profiles
- authentication state
- AI provider credentials
- local devices
- external agents and MCP tools

Never include real credentials, raw private recordings, biometric data, or private conversation history in bug reports.

## Security model

Speaker recognition and spoken passphrases are convenience controls, not strong biometric security. Privileged actions should use explicit permissions and stronger authentication where appropriate.
