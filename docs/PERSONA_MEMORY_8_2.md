# Memory Engine 2.0 and Personality Engine — experimental user controls

These helpers build on the **existing 8.1 local memory and response composer**.
No separate database, AI-generated hidden memories or duplicate intent router
is introduced.

Memory editing requires the authenticated local user. Conflicting key/value
memories are previewed and cannot be overwritten without explicit approval.
Deletion uses the existing Jervis State forgetting method. This covers
explicit memories only; historical transcripts, backups, knowledge indexes,
provider caches and remote devices have separate retention controls to be
audited before claiming comprehensive deletion.

Persona profiles store bounded 0..1 sliders for warmth, humor, directness,
expressiveness, initiative and verbosity. Only the existing allowlisted
offline reply style is currently affected: balanced, playful or focused.
Profiles have per-user hashed paths and private local files; no permissions
or factual outputs change based on persona settings.

Outstanding: Control Center and CLI editing flows, backup inclusion,
cross-channel synchronization, encrypted sensitive data stores, user-approved
semantic memory curation, retention/expiry and full behavior consistency tests.
