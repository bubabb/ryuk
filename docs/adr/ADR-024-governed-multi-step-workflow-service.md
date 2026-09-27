# ADR-024: Governed multi-step workflow service

Date: 2026-09-26  
Status: Accepted for the opt-in offline reference service

## Context

WF-014 through WF-016 define graph contracts, persistence and fenced execution,
but no authenticated caller can create or inspect a graph and no lifecycle
component schedules or recovers graph nodes. The initial-release multi-step
slice requires governed access without silently enabling background execution.

## Decision

The opt-in offline service exposes `/v1/workflow-graphs` create, status, cancel
and accepted-result routes under the existing inference role, admission quota,
tenant identity and terminal-record controls. Requests contain 1–100 bounded
nodes. Server policy owns acceptance and the aggregate deadline, attempt and
output-token budget. Schema v8 hash-binds canonical graph topology and the full
detached policy snapshot and commits graph, nodes, events, policy and budget in
one idempotent transaction; creation never dispatches inference. Dispatch reads
the saved policy, not mutable current configuration.

Status exposes node IDs and states only. Results are available only when every
terminal sink has an accepted, integrity-valid artifact and saved validation
decision. Prompts, provider bodies and unaccepted outputs are not exposed.

Graph cancellation runs in one transaction. It fences ready, running and
awaiting-validation nodes, clears leases, and lets ADR-021 deterministically
skip blocked descendants. This prevents late publication but does not claim to
cancel provider work already in flight.

`LocalGraphDispatcher` is an explicitly started, bounded local lifecycle. It
uses the server-owned tenant validation policy and the existing WF-016 executor;
construction, API creation and application startup do not start it.

Startup scans expired running graph nodes within the configured recovery bound,
increments their fences and marks them `uncertain`. It never replays inference.
An operator-only tenant-filtered route reports unresolved graph/node IDs and a
stable `outcome_unknown` reason without prompt, output or cross-tenant counts.

## Consequences and limits

- The bounded offline multi-step slice is complete from governed creation
  through accepted sink result.
- Unknown execution remains blocked for operator action and descendants do not
  run prematurely.
- There is no automatic dispatcher activation, provider cancellation,
  distributed scheduling, notification/remediation channel or production
  certification.
- Production activation remains blocked by Phase 2B, DEC-004's paid/production
  boundary and the later
  evaluation/security/certification gates.
