# Jervis Control Center 2.0 — experimental operator read-only expansion

Builds on the existing authenticated loopback-only 8.1 dashboard. Adds a
read-only summary of mission status and pending automation approvals. The UI
does not expose per-user identifiers, private content, arguments, plugin data
or remote host access. All SQL uses existing local databases opened read-only;
missing state is reported as zero rather than created on inspection.

The UI displays mission counts and an operational event timeline, using the
same local session token and origin/DNS-rebinding defenses as 8.1. Blue terminal
styling is visual only.

**Not completed:** authenticated per-user conversations, writable settings,
mission approvals, file access, remote device management, live low-latency
event streaming, CSRF-proof mutating endpoints, role-based login, accessibility
acceptance or browser compatibility certification. These must not be exposed
until the shared 8.2 capability policy is integrated at every action boundary.
