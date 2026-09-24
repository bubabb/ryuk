# ADR-009: terminal-record failure semantics

Status: implemented for the current API boundary, 2026-09-15.
Policy version: `api-control-v2`.
Scope: CP-002 and CP-003; distributed delivery guarantees remain separate.

When a record store is configured, a successful governed operation must commit
its terminal record before the API returns success. A write failure returns
503 `record_unavailable` with a safe statement that execution may have occurred.
The response does not include generated output or storage exception details.
Do not automatically rerun inference: a failed acknowledgement does not prove
that either inference or the record commit failed to take effect.

When inference, audit, or quota admission has already failed, preserve that
original failure. A failed attempt to record it emits `api.record.failed`, with
safe scalar status and code, but does not mask the original error. This is an
explicit degraded-history condition, not evidence of durable recording.

Release admission permits before recording terminal state. A store failure
must not strand an otherwise releasable permit. Coordinator outages and
process death require CP-005/CP-007; this change does not solve them.

Correlation request IDs are not execution idempotency keys. Reusing one retains
both terminal records, and each actual inference attempt has a distinct ID.
Do not deduplicate independent requests by their caller-controlled correlation
ID. No automatic retry of terminal-record writes is introduced; a future
outbox must define its own stable execution ID and deduplication protocol.

Development may omit a record store as before. Production startup continues
to require a healthy distributed durable store. There is no new configuration
switch to silently make production records optional.

Evidence: API tests inject record-store failures after success and after an
original inference failure, check sanitized responses/events, capacity release,
and two independent executions with a reused correlation ID. Existing record
store tests cover tenant separation and append behavior.
