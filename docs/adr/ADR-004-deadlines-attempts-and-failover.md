# ADR-004: Deadlines, Attempts, and Generation-Time Failover

- **Status:** Accepted
- **Date:** August 31, 2026
- **Related milestone:** C2

## Decision

The router owns a single end-to-end execution budget. It converts the task's
timezone-aware absolute deadline to a monotonic deadline once. Tasks without an
explicit deadline receive the policy's bounded default. Every health, identity,
generation, and backoff wait consumes that same budget.

Every generation try creates an immutable `ExecutionAttempt` with a unique ID,
sequence, deployment, UTC timestamps, monotonic duration, outcome, and typed
failure policy. Successful results contain the ordered attempt history. A
terminal failure retains that history only in internal diagnostic context.

Failover is bounded by `max_attempts`. `OTHER_DEPLOYMENT` advances to a different
deployment; `SAME_DEPLOYMENT` alone permits retrying the current deployment;
`NEVER` terminates immediately. Circuit-open deployment IDs are eligibility
input and are skipped, but C2 does not implement a distributed circuit breaker.
Backoff is policy-defined and must fit inside the remaining deadline.

Cancellation of an in-flight attempt cancels the awaited adapter operation and
is normalized to `CancelledFailure`. Adapter-specific remote cancellation is
deferred to C3 because the current thread-wrapped SGLang transport cannot
guarantee it.

## Consequences

Attempt order and decisions are replayable, execution is bounded, and retry
storms are constrained. Availability checks that fail before generation are not
attempts. Wall-clock timestamps are evidence only; timeout measurement is
monotonic. No failure context is exposed through the public API.
