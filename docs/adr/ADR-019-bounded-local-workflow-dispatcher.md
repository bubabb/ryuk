# ADR-019: Bounded local workflow dispatcher lifecycle

Date: 2026-09-25  
Status: Accepted for the offline single-controller reference slice

## Context

Workflow creation persists a ready task but deliberately does not execute it.
WF-005 provides an explicitly invoked executor; there was no bounded lifecycle
that could continuously select queued work, cap local concurrency, or stop
intake while allowing already-started calls to finish.

## Decision

Add an opt-in `LocalWorkflowDispatcher` around `WorkflowExecutor`.
Construction has no side effects. A caller must explicitly call `start()`; no
API route or application startup hook does so. The dispatcher is one-shot and
cannot restart after stopping.

The SQLite ready-workflow query is a bounded advisory snapshot ordered by local
insertion order. It grants no execution authority. The existing transactional
tenant/workflow claim, owner, lease and fence remain authoritative, so competing
dispatchers can observe the same candidate but cannot both execute it.

At most the configured number of local execution tasks may be active. `stop()`
closes intake first, then drains work already started. It never cancels an
external provider call or requeues ambiguous work. A caller that cannot wait
for graceful drain must treat unresolved execution according to the existing
lease-expiry and uncertain-outcome rules.

Expected claim/completion conflicts and unexpected execution exceptions are
isolated from other queued work and exposed through bounded snapshot counters
and the latest 100 tenant/workflow failure identifiers with stable sanitized
codes. No exception class, prompt, output or provider error body is included.

## Consequences and limits

- HTTP workflow creation remains non-executing.
- Local concurrency is the only admission bound added here; it does not replace
  distributed tenant quotas, cost accounting, or provider-side capacity.
- Successful inference stops at `awaiting_validation`; validation remains a
  separate persisted decision.
- There is no startup recovery orchestration, lease heartbeat, forced shutdown,
  provider cancellation, multi-controller coordination or production claim.
- An unexpected exception after claim leaves conservative durable state for
  expiry/recovery rather than inventing a safe retry.
