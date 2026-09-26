# ADR-021: Workflow dependency-graph contracts

Date: 2026-09-26  
Status: Accepted for the bounded offline contract slice

## Context

The first certified release now includes multi-step workflows, but Ryuk's
durable store, executor and APIs intentionally implement one inference task per
workflow. Multi-step persistence must not begin without stable topology,
scheduling and recovery semantics.

## Decision

`WorkflowGraph` v1 is a canonical, bounded directed acyclic graph containing
one immutable `TaskPacket` per node. A graph contains 1–100 uniquely named
nodes in sorted order. Dependencies must be unique, sorted, present in the same
graph and acyclic. Noncanonical or future-version input fails closed.

Root nodes begin `ready`; all others begin `blocked`. A node becomes `ready`
only after every direct prerequisite reaches accepted `succeeded` state.
Execution follows the existing task lifecycle: `ready`, `running`,
`awaiting_validation`, then `succeeded` or `rejected`, with existing failure,
cancellation and uncertainty states represented explicitly.

A failed, rejected or cancelled prerequisite deterministically marks blocked
descendants `skipped`; independent branches remain schedulable. An uncertain
prerequisite remains unresolved and keeps descendants blocked. Reconciliation
may move it to `awaiting_validation` or `failed`, after which normal readiness
or skip propagation applies. Illegal transitions and semantically inconsistent
state snapshots fail closed.

## Consequences and limits

- Scheduling decisions are deterministic and independent of tuple insertion,
  provider behavior or database row order.
- Acceptance—not generation alone—unlocks dependants.
- Uncertain execution never causes automatic replay or premature skip.
- The contract does not persist graphs, dispatch nodes, compose downstream
  inputs from artifacts, allocate a graph-wide budget, or add public APIs.
- WF-015 through WF-017 track those required initial-release implementation
  slices. Existing single-task behavior remains unchanged.
