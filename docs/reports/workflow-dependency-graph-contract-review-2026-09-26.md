# WF-014 workflow dependency-graph contract review

Date: 2026-09-26  
Scope: bounded offline graph and scheduler-state contracts

## Decision

WF-014 is complete for its contract scope. `WorkflowGraph` v1 defines bounded,
canonical DAG topology over existing versioned task packets. `GraphState`
defines deterministic root readiness, acceptance-gated dependency release,
legal node transitions, descendant skipping and independent-branch progress.

## Review findings

The first implementation review found that `uncertain` had been grouped with
terminal failures. That would have skipped descendants even though existing
durable recovery can later establish a successful outcome. The final contract
keeps uncertainty nonterminal and blocked: reconciliation to
`awaiting_validation` can eventually unlock descendants after acceptance, while
reconciliation to failure skips them.

The review also added invariant checks to reject manually constructed state
snapshots that bypass scheduler rules. Invalid topology, cycles, missing or
duplicate dependencies, noncanonical ordering, future versions, premature
readiness, illegal transitions and unknown nodes all fail closed.

## Limits and follow-ups

This slice does not modify SQLite, the single-task executor, dispatcher,
recovery service or API. It makes no multi-step durability or production claim.
WF-015 must persist graph/node state and atomic readiness. WF-016 must bind
artifact handoff, graph-wide budgets and node execution. WF-017 must add
governed APIs, cancellation and restart recovery before the initial multi-step
feature is complete.

## Verification

Focused graph tests: 13 passed. Full offline suite: 479 passed and 8 external
integrations deselected. Ruff passed across `backend`, `tests` and `scripts`;
Mypy passed across 122 source files; compileall, `git diff --check`, tracker
reconciliation and the repository credential-pattern scan passed.
