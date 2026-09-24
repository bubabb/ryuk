# ADR-013: single-task workflow dispatch

Status: implemented for offline execution, 2026-09-15.

`WorkflowExecutor` is the only current path that dispatches a stored workflow:
it claims one tenant-scoped workflow with an owner/fence lease, reconstructs
its validated `TaskPacket`, passes the packet's `InferenceTask` and exactly one
caller-created `WorkflowBudget` to `InferenceRouter`, then commits one terminal
artifact. Successful results include normalized output, reasoning, usage,
timing, immutable attempt snapshots and final provenance. Normalized inference
failures commit a failure artifact containing only the failure code, attempts
and budget counters; provider bodies, prompts and outputs are excluded.

A claim conflict, wrong tenant, stale owner/fence/lease or duplicate terminal
execution is rejected. No automatic replay follows an uncertain execution.
The executor has no public API and does not run automatically; this avoids
creating an ungoverned workflow route before WF-008 authentication and API
contracts. Budget limits are caller-owned for this offline slice; WF-005 callers
must persist their selected limits before dispatch once a workflow record binds
budgets durably.

This boundary does not yet perform deterministic output validation before
acceptance, so stored `succeeded` means inference completed and artifact commit
succeeded, not that quality/policy validation passed. That distinction is
required for WF-006. Live deployment, production mock containment and
high-availability guarantees remain outside this offline executor.
