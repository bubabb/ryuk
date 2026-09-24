# ADR-011: offline durable single-task workflow foundation

Date: 2026-09-15. Status: implemented foundation for offline use only.
User scope: offline implementation first; live certification pending. Inputs
are synthetic/public only, never private repositories. Hosted catalog identity
is observed, not artifact-verified. No endpoint use or spending is authorized.

The first workflow has one inference task. Workflow and task share a durable
row until dependency graphs are introduced. SQLite is the offline reference
store; production requires a separately verified distributed implementation.
Use a separate database and version marker; reject unknown schema versions.

Creation is tenant-scoped and idempotent using a caller-supplied key plus a
canonical request hash. Same key and content returns the existing workflow;
changed content is a conflict. Neither UUIDs nor keys confer tenant authority.

States: ready -> running -> succeeded/failed; ready/running -> cancelled.
An expired running lease becomes uncertain, never automatically ready. Provider
execution may have happened even without a committed result. No inference is
replayed automatically after an uncertain outcome.

Claiming uses one write transaction, a monotonic fencing token, owner ID and
UTC lease expiry. Completion requires tenant, task, owner, fence, and an
unexpired lease. Cancellation and lease recovery increment the fence so stale
workers cannot publish a result. Terminal states never return to running.
All changes append a sequenced event atomically with the state transition.

Persist request/result dictionaries only for synthetic offline fixtures at this
stage. This is not a production data-governance mechanism. Metadata APIs must
not later expose packets without authorization. Before real inputs, define
artifact storage, retention/deletion, encryption, and transaction recovery.

WF-004 through WF-008 will integrate workflow budgets, the existing router,
deterministic validation, uncertain-call reconciliation and governed APIs.
A stored succeeded state alone is not evidence that validation ran; only the
future validated executor may issue that transition through the public API.
No workflow route or automatic dispatcher is enabled by this foundation.

## WF-002/WF-003 update: typed packets and artifacts

New creation requires a version-1 `TaskPacket` wrapping the existing Ryuk
`InferenceTask`; text/chat inputs, requirements, generation, trace and deadline
are preserved. Deadlines serialize in UTC. Unknown packet versions/fields,
invalid roles and wrongly typed flags/token limits fail before persistence.
Legacy raw dictionaries remain inspectable but are never converted into an
executable task by guessing. Claims validate persisted packets before leasing.

Each terminal completion creates one immutable JSON artifact with a versioned
`ArtifactRef`, byte length and SHA-256 checksum. The artifact, result reference,
terminal state and event commit together. Reads require tenant, workflow and
artifact identifiers and verify integrity; returned payloads are detached copies.
This checksum detects corruption, not an attacker able to rewrite the database
and its checksums. Typed inference-result/provenance binding is WF-005 work.

The single task still shares its ID/row with the workflow in this vertical
slice. Dependency graphs and separately scheduled child tasks are not implied.
Lease time is evaluated after acquiring the write transaction, so lock waits
cannot extend a stale worker's completion authority.

### Offline schema migration and recovery

Database schema v2 adds the result-artifact reference and artifact table in a
single transaction. Opening v1 preserves packet bytes, result data, IDs, events,
and request hashes; it does not fabricate artifacts for prior results. Unknown
schema versions are rejected. Failed migration rolls back both DDL and version
and can be retried after removing the cause; this is fault-injection tested.

Stop all workflow writers before upgrading. This is not a rolling-upgrade
protocol: a running v1 process cannot enforce v2 artifact guarantees. Take a
consistent SQLite backup before opening the database with v2. On migration
failure, keep the unchanged v1 database and repair/retry. After successful
migration, prefer a forward fix; returning to v1 requires stopping writers and
restoring the pre-upgrade backup, losing post-backup changes. Do not manually
edit the version marker or drop the artifact table as a downgrade shortcut.
No live workflow database was migrated during this implementation.
