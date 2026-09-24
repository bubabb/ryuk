# ADR-015: offline restart recovery from durable outcome evidence

Date: 2026-09-24. Status: implemented for the offline WF-007 boundary.

The executor commits a dispatch journal before calling the router. The journal
binds tenant, workflow, claim fence and the initial budget snapshot (attempt and
output-token limits, counters, and remaining time at dispatch). It is not a
resumable budget: recovery never constructs a fresh budget or re-enters the
router. A second dispatch intent for the same workflow is rejected.

After the router returns, the executor records the normalized result or failure
in a separate transaction before completing the workflow. The journal preserves
attempts, provenance and budget consumption from the existing executor payload.
Outcome writes require the current unexpired owner/fence lease. Identical writes
are idempotent; changed content or success disposition conflicts. Journal events
commit with their writes. Provider error bodies are not added to this journal.

Recovery is explicit and internal:

1. `recover_expired(tenant)` moves expired running tasks to uncertain and
   increments their fence. Unexpired work and other tenants are untouched.
2. `reconcile_uncertain(tenant, workflow_id)` checks for a durable local outcome
   from the immediately preceding fence. With valid content/checksum evidence,
   it atomically creates the immutable artifact and transitions to
   awaiting_validation or failed, with an event.
3. Successful inference still needs the existing deterministic validation gate.
   Already completed/accepted/rejected/cancelled work is never executed again.

Missing evidence remains uncertain, including a crash before dispatch, after
committing intent but before calling the router, during a provider call, or
after a provider response but before the journal commit. Neither absence of a
result nor absence of an intent proves an external call did not happen for a
legacy/internal caller. This conservative implementation never returns uncertain
work to ready, imports an operator-supplied result, or polls a live provider.
There is no claim of exactly-once external execution or automatic resolution of
all unknown calls. External outcome lookup requires future engine-specific
contracts and authorization.

Concurrent recovery/reconciliation serializes through SQLite write transactions.
Failed artifact/event writes leave the uncertain row and journal intact for
retry. Cancellation before recovery prevents adoption of the recorded outcome;
it does not promise the external operation was stopped. Legacy direct complete
calls remain supported internally; without a journal their lost outcomes cannot
be reconstructed. No public workflow API or automatic scheduler is added.

The SHA-256 checksum detects accidental outcome-content corruption; it is not
an authentication mechanism against database writers. The database and internal
caller remain trusted, with synthetic/public inputs only. Journals contain saved
output and need the same future governance/retention treatment as artifacts.

## Schema v4

Schema v4 adds workflow_dispatches transactionally. v3 rows, artifacts, acceptance
reports and events are preserved; no dispatch/outcome evidence is fabricated.
v1/v2 also retain ADR-014's migration of old successes to awaiting_validation.
Migration errors roll back the version marker and new table together.

Stop all writers and take a consistent SQLite backup before opening an existing
database with v4. This is not a rolling-upgrade protocol. Prefer forward repair;
rollback requires stopping writers and restoring the pre-upgrade backup, losing
post-backup writes. Never manually lower the schema marker. Only synthetic test
databases were migrated in this work. SQLite remains an offline reference store.
