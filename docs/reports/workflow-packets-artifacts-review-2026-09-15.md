# WF-002/WF-003 offline implementation review

Scope: typed task packets and durable artifact records on the single-task
SQLite foundation. Live certification remains pending; all tests use synthetic
inputs and explicitly deselect external integrations.

## Completed

- TaskPacket v1 wraps Ryuk's existing inference types and preserves text/chat,
  hard requirements, generation settings, trace and UTC-normalized deadline.
- New workflow creation rejects raw dictionaries and invalid typed packets.
  Canonical serialization preserves idempotency semantics.
- Completion atomically stores a versioned, checksummed JSON artifact, its
  reference, terminal state and event. Failed completion rolls all of them back.
- Artifact access checks both tenant and workflow; reads validate integrity and
  return detached content. Duplicate/stale/cancelled completions create no
  extra artifact. Successful and failed results use the same storage mechanism.
- SQLite v1-to-v2 migration preserves old records and rejects unknown versions.
  Invalid legacy packets remain readable as history but cannot be claimed as
  inference tasks. A denied artifact-table creation rolls back migration and
  version advancement; reopening after fault removal succeeds.

## Review finding and correction

The earlier foundation checked completion time before taking the transaction.
A database lock wait could therefore allow a worker to commit after its lease
expired. The clock check now runs inside the transaction. A controlled lock-wait
regression proves late completion is rejected without publishing an artifact.
Claim and recovery timestamps also run inside their transactions.

Review traced packet validation, canonical replay, all tenant filters, completion
atomicity, migration failure, event rollback and late/duplicate results. No
unresolved blocking finding remains in this implemented scope.

## Validation

- Full offline suite: **282 passed, 8 external integrations deselected**.
- Workflow suites: 26 cases included in the passing offline suite.
- Ruff passed; Mypy passed across 85 source files.
- Compilation and diff whitespace checks passed.

## Limits and next task

WF-002 and WF-003 are complete for the documented single-task offline scope.
WF-004 is next: one workflow deadline and budget across router attempts.
Dispatch, deterministic acceptance, reconciliation and public APIs remain
WF-005 through WF-008. No public workflow route or autonomous worker is enabled.

Artifacts hold versioned JSON objects; this change does not claim encryption,
retention/deletion enforcement, cryptographic signing, arbitrary process-crash
certification, or distributed production readiness. The result-to-model and
attempt binding must be validated when dispatch is connected. Migration requires
stopped writers; ADR-011 documents backup and roll-forward/restore behavior.
