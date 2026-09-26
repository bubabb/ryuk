# ADR-023: Fenced workflow graph execution and shared budget

Date: 2026-09-26  
Status: Accepted for the offline SQLite reference slice

## Context

Schema v6 persists graph topology and scheduler state but intentionally grants
no execution authority. Multi-step execution requires the same safety
properties as single-task workflows plus accepted-only dependency handoff and
limits that cannot reset between nodes or after process restart.

## Decision

Schema v7 adds graph-node owner/fence/lease fields, immutable graph budget
records and graph result artifacts. A node is claimable only while `ready`,
before the graph deadline, and after a budget has been bound. Claiming is
tenant-scoped, atomic and fenced. Completion requires the same owner, fence and
unexpired lease; late or foreign results cannot publish an artifact.

One durable graph budget owns an absolute deadline, aggregate attempt ceiling
and aggregate output-token ceiling. Router attempt reservations and observed
output-token accounting update that record transactionally, so parallel nodes
and process restarts cannot mint fresh limits.

`GraphNodeExecutor` executes exactly one claimed node through the existing
typed router. Direct dependencies must already be accepted. Their immutable
artifact IDs, hashes and accepted `output` objects are serialized in canonical
dependency order into a versioned Ryuk-owned envelope appended to text input or
as a final user message for chat input. Unaccepted, missing or integrity-invalid
artifacts fail closed.

Successful inference is stored as `awaiting_validation`; deterministic artifact
validation then marks it `succeeded` or `rejected`. Only accepted success
releases dependants. Normalized inference failure stores a sanitized failure
artifact with attempt evidence and marks descendants skipped. Unhandled process
failure leaves the fenced node running; this path never automatically replays.

## Migration

Schema v6 migrates transactionally to v7. Existing graph/node state is
preserved, new fence counters start at zero, and no budget or execution
authority is invented. Migration failure rolls back columns, tables and schema
version and may be retried safely.

## Consequences and limits

- Node execution, artifacts and aggregate graph limits survive restart.
- Dependency content is explicit and hash-bound instead of ambient shared
  memory.
- Input-token and monetary accounting remain WF-013; unknown usage is not
  converted to zero.
- There is no public graph API, graph-wide cancellation, lease-expiry recovery,
  dispatcher integration or operator reconciliation yet. WF-017 owns these.
- SQLite remains an offline single-controller reference, not a production or
  distributed execution claim.
