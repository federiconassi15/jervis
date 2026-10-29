# Jervis 8.2 Automation Builder — safe declarative foundation

This source module stores per-owner event-triggered rules, prevents duplicate
event processing, enforces cooldowns and emits pending approval requests.

It deliberately **does not execute any command** or accept code, arbitrary
Python, shell scripts or model-written actions. Rules are initially disabled
until an authenticated owner enables them. Matched actions must later be sent
through Mission Control's capability checks.

The GUI builder, actual event-bus integration, timezone-aware scheduling,
notification backends, background service recovery and signed external
integrations are not yet implemented or tested. Do not label this a finished
automation product or enable external write operations.
