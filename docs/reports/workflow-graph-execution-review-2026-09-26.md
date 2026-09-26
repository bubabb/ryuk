# WF-016 fenced workflow graph execution review

Date: 2026-09-26  
Scope: offline fenced graph-node execution, accepted-artifact handoff and durable graph budget

## Decision

WF-016 is complete for its bounded offline scope. Graph nodes now use atomic
owner/fence leases, immutable result artifacts, deterministic validation and a
single durable attempt/output-token/deadline budget shared across all nodes.
Accepted predecessor artifacts are bound explicitly into dependent input by ID,
hash and canonical output payload.

## Review findings

The review exercised successful handoff, rejection/descendant skip, budget
exhaustion across nodes, budget persistence, concurrent attempt reservation,
stale leases, tenant scoping, artifact integrity and v6-to-v7 migration.

The implementation preserves normalized failure attempt evidence rather than
recording only a failure code. Budget binding is immutable and idempotent for
the same ceilings; rebinding different ceilings fails. A process crash after
claim leaves a running fenced node and cannot silently reclaim or replay it.

No unresolved defect remains within this scope. The prior WF-015 audit-order
fix remains intact, and accepted dependency lookup verifies both graph state
and artifact acceptance before input composition.

## Limits and follow-ups

WF-017 must add governed graph APIs, dispatcher integration, cancellation and
startup reconciliation. Until then, graph execution is an explicitly invoked
internal offline operation. There is no provider cancellation claim, input-token
or monetary enforcement, production activation or distributed scheduler.

## Verification

Focused graph contract/store/executor tests: 32 passed. Full offline suite: 498
passed and 8 external integrations deselected. Repository-wide Ruff passed;
Mypy passed across 126 source files; compileall, tracker reconciliation,
`git diff --check` and credential scanning passed.
