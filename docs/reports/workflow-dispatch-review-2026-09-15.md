# WF-005 offline dispatch review

`WorkflowExecutor` binds one stored workflow claim to one `InferenceTask`, one
shared `WorkflowBudget`, router failover attempts, and one terminal artifact.
Success artifacts contain normalized output/reasoning, usage, timing, final
provenance and every immutable attempt snapshot. Failure artifacts contain only
normalized failure code, attempts and budget counters, with no provider error
body or prompt. Tenant filters and owner/fence leases are enforced by the
store; duplicate or stale execution cannot publish a second result.

Review found and corrected a router type-checking issue where output-token budget
exhaustion reused an exception variable from an `except` block. The final router
has distinct budget-failure variables and passes Mypy.

Validation:

- Full offline suite: **290 passed, 8 external integrations deselected**.
- Ruff passed.
- Mypy passed across 89 source files.
- Compileall and `git diff --check` passed.

WF-005 is complete for the offline single-task boundary. This executor is not a
public route and does not claim deterministic validation, durable budget
configuration, uncertain-call reconciliation, or production dispatch. WF-006
is next: run deterministic validation before committing workflow acceptance.
