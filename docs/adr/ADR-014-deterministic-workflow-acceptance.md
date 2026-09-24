# ADR-014: deterministic workflow acceptance

Date: 2026-09-23. Status: implemented for offline internal use (WF-006).

Inference completion and task acceptance are separate transitions. Successful
`complete()` and `WorkflowExecutor.execute()` now produce `awaiting_validation`,
with the immutable inference artifact already committed. Inference failure
still produces `failed`. Only `SQLiteWorkflowStore.validate()` can advance an
awaiting result to `succeeded` (accepted) or `rejected`. Validation never mutates
the inference artifact, repeats inference, or changes attempts/budget counters.
Cancellation is allowed while awaiting validation; a cancelled result cannot
subsequently be accepted. Validation and cancellation serialize on the same
write transaction, so the first committed terminal decision wins.

The caller supplies Ryuk's existing `ValidationPolicy`. The internal caller is
trusted to select policy; no public API or automatic dispatcher is introduced.
The first committed decision fixes the complete detached policy snapshot,
validator version, artifact ID/checksum, workflow ID, decision and findings.
Identical replay returns the stored report, including after restart, and does
not append another event. A different policy or artifact is a conflict, even
for a rejected result. Policies must be bound to authorized task criteria
before exposing a governed workflow API in WF-008; this internal interface is
not an authorization mechanism or production policy decision.

Validation reads the tenant/workflow-scoped artifact and verifies its checksum.
Report, terminal state and event commit in one transaction. Exceptions leave
the result awaiting validation; no report or acceptance is partially committed.
Only saved output.text is checked, not provider reasoning. Missing/empty text
is rejected. Existing audit rules supply required-section substring checks,
length limits, citations, ASCII language checks, forbidden phrases, secret
patterns and the supported flat JSON object-schema subset. Any finding rejects
this deterministic gate, including language warnings. Unknown language/schema
rules are rejected instead of silently ignored. JSON duplicates and nonfinite
numbers are invalid. Reports contain generic finding codes rather than output
snippets or dynamic field names. Policy snapshots may contain caller-provided
rule strings and are subject to the same offline-only data scope as packets.

This is deterministic format/policy acceptance, not factual verification,
model auditing, full JSON Schema support or calibrated quality evaluation.
Sections use the existing case-insensitive substring semantics, not a Markdown
parser. Nested object/array contents are not schema-validated; only top-level
property types, required keys and additional properties are supported.

## Schema v3 migration

Schema v3 adds workflow_validations. Opening v1/v2 upgrades transactionally;
old succeeded rows become awaiting_validation with an appended transition
event, preserving historical events and artifacts. No old result is silently
accepted. Legacy rows without artifacts remain inspectable but cannot validate;
this implementation does not invent missing evidence or rerun their inference.
Failed migration rolls back the schema marker, table and state/event changes.

Stop all writers and take a consistent backup before upgrading. Old workers
must not run against v3: they could write succeeded without validation. This
is not a rolling upgrade. Prefer a forward fix after migration; rollback
requires stopping writers and restoring the pre-upgrade backup, with loss of
post-backup changes. Do not manually downgrade the schema marker. Only synthetic
test databases were migrated during development.
