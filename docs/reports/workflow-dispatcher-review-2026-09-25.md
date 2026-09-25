# WF-010 bounded local dispatcher review

Date: 2026-09-25  
Scope: offline SQLite single-controller reference implementation

## Decision

WF-010 is complete for its approved offline scope. `LocalWorkflowDispatcher`
requires explicit start, enforces a configured local concurrency ceiling, uses
the existing transactional claim/fence as execution authority, stops intake
before graceful drain, isolates task failures, and exposes bounded sanitized
failure observations. API creation and application startup do not instantiate
or start it.

## Review findings

A separate implementation review found and corrected one misleading metric:
conflicts can happen after claim as well as during claim, so the final snapshot
uses `workflow_conflicts` rather than `claim_conflicts` and records the affected
tenant/workflow with a sanitized code. No unresolved correctness issue remained
after that correction.

The ready-list query is intentionally advisory and bounded; claim remains
atomic. Concurrency tests hold two calls open and prove a maximum of two while
four workflows across two tenants complete. Shutdown tests prove that an
already-started call drains and a later queued workflow remains ready. An
unexpected router exception remains fenced in running state for conservative
recovery, is observable, and does not prevent the next workflow from executing.
Construction and API creation remain side-effect free.

## Limits

This is not a production scheduler. It has no automatic startup activation,
startup recovery, lease renewal, provider cancellation, cost admission,
distributed coordination or forced-stop guarantee. Graceful shutdown may wait
for a provider call; callers must apply an outer operational deadline and then
use the existing uncertain-outcome process rather than replaying blindly.
WF-011 remains a separate startup-recovery change set.

## Verification

Focused dispatcher/executor/store tests: 20 passed. Full offline suite: 393
passed and 8 external integrations deselected. Ruff passed; Mypy passed across
108 sources; compileall and `git diff --check` passed.
