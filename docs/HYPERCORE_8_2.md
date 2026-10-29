# Jervis HyperCore 2.0 policy engine (experimental)

This is an independently testable routing *decision engine*, not a new model
runtime. It reuses 8.1's deterministic local intent allowlist and can select
among declared providers using privacy classification, explicit cloud consent,
health status, complexity, cost budget, latency estimate and circuit breakers.

**No prompts are sent to models, and no actions are executed by this module.**
Even an authorized route cannot override the permission engine. The provider
adapter must enforce the selected privacy policy again at the network/tool
boundary. The policy must not log or cache private user messages.

Not yet completed: integration with the runtime BrainRouter, provider adapters,
accurate cost/latency telemetry, half-open trial serialization, model warm-up,
provider failure compensation, hardware performance measurement and user-facing
explanation UI. The design remains portable and uses the existing 8.1 FastRouter.
