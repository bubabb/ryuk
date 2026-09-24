# ADR-016: governed offline workflow API and creation-time policy binding

Date: 2026-09-24. Status: implemented for WF-008's offline single-task boundary.

Four opt-in routes use the existing shared API control plane:

| Route | Role | Behavior |
| --- | --- | --- |
| POST /v1/workflows | inference or admin | Atomically save one ready task and its policy/budget binding; return 202 |
| GET /v1/workflows/{id} | inference or admin | Return workflow ID, state, bound policy version and result availability |
| POST /v1/workflows/{id}/cancel | inference or admin | Fence running work or cancel ready/awaiting work; repeated cancellation is stable |
| GET /v1/workflows/{id}/result | inference or admin | Return only an accepted, integrity-checked result and its bound validation report |

Authentication derives tenant authority from the API key. An optional x-tenant-id
header must match that authority. Operator-only credentials cannot use these
routes; admin does not bypass tenant isolation. Missing and foreign workflow IDs
both return 404. Unknown body fields (including tenant, policy, budget and state)
are rejected. Legacy rows without creation bindings are not exposed by this API.

Creation currently supports text tasks with explicit model preference, generation
limits and temperature. A separate server-owned JSON file maps each tenant to
one versioned acceptance policy and execution budget. No tenant entry means no
create permission. The snapshot is detached and saved atomically with the task
and initial event. The authenticated tenant's server policy is the acceptance
criteria; clients cannot weaken it or provide a policy at result retrieval.
The supported configuration rules are required sections, citations, length,
forbidden phrases and ASCII language. JSON-schema configuration and chat creation
are not exposed in this first route contract.

Idempotency covers the complete normalized task and bound policy/budget. The
trace identifier is derived deterministically from tenant plus idempotency key,
so HTTP request correlation IDs cannot invalidate replay. Same tenant/key/input
and policy returns the same workflow, including after restart or a lost HTTP
acknowledgement. Changed task or binding returns 409. Policy changes do not alter
existing work; a create retry against a changed policy conflicts rather than
silently rebinding it. Reading existing work does not require the current policy
configuration to still contain its original definition.

All routes use request-rate/concurrency admission. Creation additionally charges
requested output tokens multiplied by the authorized attempt limit; this is a
conservative admission estimate, not measured provider billing. Replay attempts
also pass admission. Permits are released on success, conflict, persistence
failure and cancellation. Terminal API records contain operation/status only,
without packets, outputs or policy strings, using ADR-009's existing failure
semantics. A record failure after creation returns 503; the same idempotency key
can recover the already-created task without executing inference.

Creating a workflow queues it and never calls a provider. No automatic dispatcher,
public execute/validate/recovery route or background task is added. The existing
internal WorkflowExecutor constructs the saved budget for bound work and rejects
caller budget overrides; unbound offline fixtures retain their old explicit
budget interface. The execution deadline starts at dispatch, not at queue entry.
This does not implement distributed worker admission or a durable token ledger;
those remain production work. Internal dispatch must still be explicitly
invoked in the authorized offline environment.

SQLiteWorkflowStore.validate uses the bound snapshot by default for API-created
work. An explicit different policy conflicts. Recovery still ends at
awaiting_validation, and unknown outcomes remain uncertain. Result retrieval
rechecks the saved artifact/decision/policy binding; unaccepted, failed, rejected,
cancelled and uncertain work returns 409 without exposing saved output.
Cancellation does not claim that an already-started external operation stopped.

WORKFLOW_STORE_PATH and WORKFLOW_POLICY_CONFIG_PATH must be configured together.
Both are unset by default, and production settings reject this offline workflow
configuration. Synthetic/public inputs only; this implementation is not approval
for real provider use or production data retention.

## Schema v5 and migration

Schema v5 adds workflow_bindings in the same migration transaction as the version
marker. Existing task bytes, hashes, states, journals, artifacts, validation
reports and events are preserved; no authority is fabricated for legacy work.
Earlier schema migration guarantees from ADR-014/015 still apply. Failure rolls
back table creation and the version marker together.

Stop all writers, take a consistent backup, and only then open an older database
with v5. Old writers must not run against v5 because they do not enforce policy
binding. Prefer forward repair. Rollback requires stopping writers and restoring
the pre-upgrade backup, with loss of post-backup writes. No live database was
migrated in this implementation.
