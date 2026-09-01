# Deterministic Routing Policy

F1 introduces policy version `ryuk-deterministic-v1`. D1 hard constraints run
first and permanently remove incompatible candidates. The policy cannot assign
a score to, or restore, a rejected deployment.

Eligible deployments receive integer components for explicit engine preference,
fresh readiness, recent attempt reliability, known available capacity, context
headroom, configured cost and latency classes, and curated task suitability.
Unknown evidence contributes zero rather than an invented favorable value.
Exact score ties preserve deployment registration order.

The preference component is intentionally dominant in v1, but it is still soft:
an incompatible preferred engine is filtered and another eligible deployment can
execute. Cost/latency classes and suitability are configured deployment policy
evidence; they are not inferred from engine names. F2 will measure whether these
rules improve outcomes before changing weights.

Every successful result records the policy version, ordered deployment IDs,
candidate totals, named components, and concise explanations. Combined with C2
attempt records, this makes the selection and subsequent failover replayable.
