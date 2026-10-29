# Mission Control 8.2 — durable execution core (experimental)

This initial module supports sequential registered steps, durable SQLite status,
scope/role/device authorization and restart recovery. It deliberately has no
shell, network, agent or arbitrary-plugin executor. No model-generated action is
trusted. On crash, idempotent running steps may be requeued; non-idempotent
running steps become blocked for operator review. Any actual external handler
must independently implement idempotency.

This is **not a finished Mission Control product**: DAG scheduling, tool
execution isolation, GUI review, rollback policies, multi-process leases,
workflow editing and OS-specific acceptance are still necessary. The mission
database currently stores plaintext payloads; it must be protected locally and
included in audited backup/migration policies before general deployment.
