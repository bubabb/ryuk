# WF-017 governed multi-step workflow review

Date: 2026-09-26  
Scope: opt-in offline graph APIs, dispatcher, cancellation and startup recovery

## Decision

WF-017 is complete for the approved offline scope. Authenticated tenants can
create bounded policy-bound graphs, inspect sanitized node state, fence/cancel
the graph and retrieve accepted sink results. An explicit local dispatcher can
execute ready nodes, and startup recovery conservatively fences expired work as
uncertain without replay.

## Review findings

The review verified authentication and roles, tenant isolation, missing-policy
denial, topology rejection, input limits, idempotency, result gating, terminal
records, cancellation fencing, dependency skip, recovery isolation and explicit
dispatcher lifecycle.

Three implementation defects were found and corrected before closure. First, the
new dispatcher class was initially inserted before the original dispatcher's
remaining private methods, which would have assigned methods to the wrong
class. Class boundaries were repaired and both dispatcher suites pass. Second,
graph creation and budget binding initially used separate transactions. The
final API hash-binds the server budget and creates graph, nodes, events and
budget atomically; injected event failure leaves none of them behind. Third,
only the budget was initially durable, allowing later policy configuration to
change validation of an existing graph. Schema v8 now hash-binds and stores the
complete detached server policy, and dispatch reconstructs that exact snapshot.

No unresolved defect remains within this scope. Cancellation fences state but
does not assert provider cancellation. Expired work becomes uncertain and is
never automatically reclaimed.

## Limits and follow-up

The graph dispatcher remains explicit and local. Production, live providers,
input-token/cost enforcement, external cancellation, distributed HA and final
evaluation/certification remain separately gated. After WF-017 no tracker item
is READY: continuing the critical path requires reopening deferred DEC-004 for
controlled Phase 2B access or an explicit owner-approved change to another
recorded phase gate.

## Verification

Focused graph/workflow contract, store, executor, API, dispatcher, recovery and
validation tests: 76 passed. Full offline suite: 509 passed and 8 external
integrations deselected. Repository-wide Ruff passed; Mypy passed across 129
source files; compileall, tracker reconciliation, `git diff --check` and
credential scanning passed.
