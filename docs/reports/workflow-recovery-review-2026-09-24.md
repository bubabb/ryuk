# WF-007 offline restart recovery review

Date: 2026-09-24. Scope: synthetic/public local fixtures only.

The executor now journals dispatch intent and returned outcomes. Explicit lease
recovery fences stale workers; reconciliation can finish a locally recorded
outcome without contacting an engine. Missing evidence remains uncertain and
unclaimable. Recovered success still requires artifact-bound validation.
ADR-015 documents schema v4, crash windows and operational limitations.

Evidence in tests/test_workflow_recovery.py and the existing workflow suites:

- Failure injection before dispatch, after intent, after the router returns,
  before final completion, and after completion; restart does not add engine calls.
- Abrupt subprocess exit without closing SQLite preserves a committed outcome.
- Two connections recovering/reconciling concurrently produce one artifact/event.
- Wrong tenants, stale owner/fence, expired outcome writes, duplicate dispatch,
  conflicting journal replay, cancellation and corrupt outcomes fail closed.
- Outcome, recovery and reconciliation event failures roll back their transactions
  and can be retried without partial artifacts or state transitions.
- Schema v3 migration preserves existing work; injected failure rolls back the
  new table/version. Legacy missing evidence remains uncertain after expiry.
- Existing validation replay and acceptance stay separate from inference recovery.

Full verification counts are recorded in PROJECT_STATUS_REPORT.md and the session
handoff. External certification remains pending. Unknown provider outcomes cannot
be automatically resolved; live lookup, distributed recovery, retention policy,
and public workflow authorization are outside this offline implementation.
