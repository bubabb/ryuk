# Offline workflow foundation review

Historical checkpoint: typed packet/artifact work is now covered by
`workflow-packets-artifacts-review-2026-09-15.md`, which supersedes the
WF-002/WF-003 status and next-step notes below.

Owner scope recorded 2026-09-15: offline implementation first; leave live
certification pending. Synthetic/public test data only, no private repositories,
and catalog identity is observed rather than artifact-verified.

## Implemented slice

ADR-011 and `backend/workflows/store.py` provide a single-task SQLite reference
store, canonical-input idempotency within each tenant, sequenced atomic events,
transactional claims, owner/fence/lease checks, cancellation, and restart lease
recovery. An expired running task becomes uncertain and cannot be reclaimed.
Completion of cancelled, expired, foreign-tenant, wrong-owner, or stale-fence
work is rejected. Two database connections racing to claim a task yield one
winner. Event insertion failure rolls back the corresponding state change.
Unknown schema versions are rejected rather than migrated speculatively.

## Review and evidence

Review traced each mutation through its transaction and tenant filter; examined
rollback, duplicate creation/completion, lease expiry, event ordering and
cancellation invalidation. No blocking defect was found in this foundation.

- Workflow contract suite: 10 passed.
- Full test suite: 266 passed, 8 optional external-service tests skipped.
- Ruff passed; Mypy passed across 83 source files.
- Python compilation and `git diff --check` passed.
- No live inference, infrastructure provisioning, or spending was performed.

For subsequent offline runs explicitly select `python -m pytest -m 'not
integration'` to exclude external integrations even if credentials are later
present in the environment.

## Scope limits and next implementation

WF-001 is complete for the offline single-task foundation. WF-002 remains in
progress: typed inference packets and artifact contracts are not yet complete.
WF-003 has its storage-level evidence, with integration still pending WF-002.
The completed reference methods are not yet public workflow APIs.

Budgets, router dispatch, deterministic task acceptance, artifact persistence,
uncertain-call reconciliation and authenticated workflow APIs still need their
separate implementation and failure tests (WF-004 through WF-008). The store's
terminal `succeeded` transition is an internal primitive, not a public promise
that model output was validated. Do not expose it directly to API callers.

This foundation uses raw JSON packets for synthetic fixtures and a combined
workflow/single-task row. It does not implement production data governance,
separate graph tasks, high availability, lease heartbeats, external queues,
provider cancellation or automated uncertain-call replay. SQLite concurrency
tests do not certify distributed infrastructure or arbitrary process-crash
boundaries. The full roadmap and Phase 3 exit gate remain unfinished.
