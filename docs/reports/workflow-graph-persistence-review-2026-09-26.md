# WF-015 durable workflow graph persistence review

Date: 2026-09-26  
Scope: offline SQLite graph/node persistence and atomic readiness

## Decision

WF-015 is complete for its bounded persistence scope. Schema v6 stores
canonical tenant-scoped graphs, individual node state and ordered graph events.
Creation is hash-bound and idempotent; transitions and all derived scheduler
changes commit in one transaction.

## Review findings

The review checked tenant isolation, restart reconstruction, idempotency
conflicts, malformed inputs, corrupt/incomplete rows, transaction rollback,
concurrent writers, bounded ready snapshots and v5-to-v6 migration rollback.

One audit defect was found: although updates were atomic, iterating canonical
node IDs could record a derived descendant event before the causal prerequisite
when identifiers were not topologically ordered. The final implementation
records the requested transition first and derived changes in stable
prerequisite-first order. A deliberately inverted-ID regression proves the
event sequence.

No unresolved defect remains within this scope. The store reconstructs
`GraphState`, so database tampering that removes a node or violates scheduler
invariants is rejected rather than silently scheduled.

## Limits and follow-ups

There is no graph-node lease, fence, dispatch journal, artifact handoff,
graph-wide budget, public API, cancellation propagation or startup recovery in
this slice. The ready listing is explicitly advisory. WF-016 and WF-017 track
those required initial-release capabilities.

## Verification

Focused graph contract/store tests: 25 passed. Full offline suite: 491 passed
and 8 external integrations deselected. Repository-wide Ruff passed; Mypy
passed across 123 source files; compileall, tracker reconciliation,
`git diff --check` and credential-pattern scanning passed.
