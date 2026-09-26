# ADR-022: Durable workflow graph and node state

Date: 2026-09-26  
Status: Accepted for the offline SQLite reference slice

## Context

ADR-021 defines deterministic dependency-graph topology and transitions, but
does not survive restart or coordinate concurrent writers. The initial release
requires durable multi-step scheduling without weakening the existing
single-task store's tenant, idempotency, transaction and migration guarantees.

## Decision

Workflow schema v6 adds tenant-scoped graph, graph-node and graph-event tables.
Graph creation validates and canonicalizes `WorkflowGraph` v1, hashes the exact
canonical graph for tenant-scoped idempotency, and creates every initial node
state and event in one transaction. Reusing a key with different graph content
fails closed.

Persisted reads reconstruct both the graph and `GraphState`; missing, corrupt or
semantically inconsistent node state fails closed. A graph-node transition
loads the authoritative state under `BEGIN IMMEDIATE`, applies ADR-021, and
commits the requested transition plus all derived readiness or skip transitions
atomically. Events are recorded in causal order: the requested prerequisite
transition first, then derived descendants in stable topological order.

A bounded ready-node listing is advisory only. It does not claim work or grant
execution authority. Concurrent attempts to perform the same transition
serialize, and only the first legal transition commits.

## Migration

Schema versions 1–5 migrate transactionally to v6. Existing single-task rows
are preserved and no graph is invented for them. Failure while creating any v6
table or updating the version rolls back the entire migration, allowing a safe
retry after the fault is removed.

## Consequences and limits

- Graph topology, node state and audit history survive restart.
- Dependency release and descendant skipping cannot be partially committed.
- Tenant-qualified reads do not reveal another tenant's graph or events.
- WF-016 must add fenced node claiming/execution, exact accepted-artifact input
  binding and one graph-wide budget. Until then, ready nodes are not executable.
- WF-017 still owns governed APIs, graph cancellation and startup recovery.
- SQLite remains an offline single-controller reference, not a distributed
  scheduler or production durability claim.
