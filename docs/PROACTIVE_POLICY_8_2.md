# Jervis 8.2 proactive delivery policy (experimental)

Builds alongside the existing 8.1 ProactiveEngine. This policy module
returns deliver/defer/discard decisions based on user presence, busy state,
quiet hours, event expiry, cooldown and event deduplication. A critical
event may bypass quiet hours and ordinary rate limits, but never bypasses
absence/busy checks or any authorization. No background monitoring,
notification source, microphone or network integration is added.

Delivery history is bounded and in-memory, containing only user identifiers,
event codes, timestamps and event IDs, not notification bodies. A future
durable database and actual ProactiveEngine integration must preserve
privacy and repeat suppression across restarts. No autonomous action or
unconsented external watch is enabled by this change.

Correctness gates: recorded delivery requires a valid candidate, quiet
hours, rate limits and event replay are tested. Device wake and actual
notifications remain subject to OS and user permission gates.
