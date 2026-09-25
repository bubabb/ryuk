# Offline Phase 3 exit review

Date: 2026-09-25  
Planning authority: `RYUK_DEVELOPMENT_PHASE_PLAN.md`  
Scope: offline, single-task workflow; synthetic/public inputs only. No live
provider or production evidence was gathered for this review.

## Decision

The Phase 3 exit criterion is **met for the offline single-task slice**: tests
exercise restart across durable workflow state and dispatch boundaries, preserve
attempt/provenance evidence, reconcile only recorded outcomes, reject stale
fences, and require a separate persisted validation decision before acceptance.
Relevant evidence is in `tests/test_workflow_store.py`,
`tests/test_workflow_recovery.py`, `tests/test_workflow_validation.py`,
`tests/test_workflow_api.py`, and the WF-005–WF-008 review reports. At review
time the complete offline suite passed: 367 passed, 8 external integration
tests deselected; Ruff, targeted Mypy, and `git diff --check` passed.

This decision does **not** claim completion of every operational step in the
broader phase plan. Workflows can be created through governed routes, but
dispatch and recovery are explicitly invoked internal operations. No background
scheduler starts work or runs recovery at application startup. Cancellation
fences Ryuk state and late result commits but does not stop a provider call.
Budgets cover one deadline, attempt count and optional output-token ceiling;
there is no durable input-token or monetary budget/usage ledger. SQLite and
current admission estimates are offline references, not distributed worker
admission or production persistence. No real deployment was used to prove
provider cancellation, billing, failover, or production recovery.

CTX-001 may proceed as **offline Phase 4 context-preparation design and
implementation**. The scope remains synthetic/public, and Phase 2B, tool
execution, live activation and production certification gates remain closed.

## Reconciliation with Phase 3 plan

| Plan requirement | Evidence and disposition |
| --- | --- |
| Typed workflow/task/packet/artifact and budget contracts | Implemented across ADR-011/012 and WF-002/WF-004; this vertical slice stores one inference task per workflow. A dependency graph is not implemented. |
| Explicit states; distinguish inference from acceptance | Implemented. Inference completes to `awaiting_validation`; a separate deterministic decision accepts or rejects. |
| Versioned transitions and ordered immutable events | Implemented and transactionally tested in the workflow store and migrations. |
| Transactional claim, lease and fencing | Atomic claim/fencing implemented and race-tested. There is no autonomous scheduler/worker loop. |
| Shared workflow budget | One deadline, max attempts and optional output-token ceiling flow through router attempts. Input-token and monetary cost budgets are not implemented; usage is not a durable billing ledger. |
| Dispatch through the existing inference router with provenance | Implemented by `WorkflowExecutor` as an explicit internal call; no automatic dispatch from queue/API creation. |
| Durable result artifact, deterministic validation, idempotent create/replay | Implemented and covered by WF-006/WF-008 reports and tests. Validation is deterministic policy/format validation, not factual verification. |
| Startup recovery of expired/uncertain work | Store operations explicitly recover and reconcile with durable evidence; recovery is not automatically orchestrated at startup. Unknown outcomes remain uncertain and are never replayed automatically. |
| Cancellation to queued/running inference and late-result handling | API cancellation and fencing prevent acceptance of stale/late outcomes. Cancellation is not propagated to or confirmed by external providers. |
| Tenant-scoped create/status/cancel/result API | Implemented in WF-008 with server-bound policy/budget, authorization, idempotency and accepted-result checks. There are no public execute, validate or recovery routes. |
| Exit gate: one model task survives controller restart without duplicate accepted work, lost provenance or inconsistent status | Met for the tested offline SQLite boundary. Process-exit/reopen and restart tests cover dispatch uncertainty, artifact/result persistence, validation replay and fencing. This is not a distributed or production durability claim. |

The phase plan's `TaskDependency` concept is broader than the current one-task
vertical slice. Keep that graph deferred until a multi-step workflow phase
requires it; do not block the bounded Phase 3 exit on an unused graph model.

## Tracked follow-up work

| ID | Status | Follow-up | Dependency / gate |
| --- | --- | --- | --- |
| WF-010 | HOLD | Add a bounded local dispatcher/worker lifecycle for queued workflows, with explicit concurrency and shutdown behavior | Separate approved execution scope; do not enable provider execution through API creation |
| WF-011 | HOLD | Orchestrate expired-lease recovery and uncertain-outcome reconciliation during service startup, with operator-visible unresolved outcomes | WF-010; preserve no-automatic-replay rule |
| WF-012 | HOLD | Add and verify end-to-end cancellation propagation and late-result behavior for each supported provider | P2B-001 through P2B-004 and provider contract evidence |
| WF-013 | HOLD | Define durable input-token/usage accounting and cost-budget enforcement for workflow execution | DEC-006, provider usage evidence and approved billing terms; token limits alone do not establish dollar cost |
| WF-014 | HOLD | Add dependency-graph/task scheduling contracts if multi-step orchestration is approved | A later multi-step workflow scope; not needed for the one-task slice |

Distributed execution and shared quota/fencing work remain covered by CP-005,
CP-006, CP-007 and PROD-001. They are not duplicated here. These follow-ups
and Phase 2B remain separate from the offline Phase 3 exit decision.
