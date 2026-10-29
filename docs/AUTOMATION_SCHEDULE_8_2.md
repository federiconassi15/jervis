# Scheduled automations (8.2 experimental)

This extends the existing \`AutomationStore\` event-rule system without replacing
its rule schema or authorization policy. Enabled schedules translate intervals
or timezone-aware local clock times into deduplicated event IDs; the existing
approval queue receives pending requests. **Nothing is executed by this module.**

Features: intervals 60 seconds–30 days, IANA timezone daily time, DST gap skip,
DST fold first occurrence, disabled-by-default, per-owner polling, at-most-one
event per scheduled timestamp, and missed backlog collapse after downtime.

Still required for a full product: trusted host lifecycle integration, a
service-side identity/capability policy for unattended operation, editing UI,
end-to-end persistence/migration tests, cancel/retry semantics, observability
and physical power-loss tests. It must not fake owner login to run schedules.
