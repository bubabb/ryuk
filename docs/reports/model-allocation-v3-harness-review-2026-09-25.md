# EVAL-004 model-allocation v3 harness review

Date: 2026-09-25  
Scope: offline evaluation tooling only; no model calls

## Decision

EVAL-004 is complete. The manifest loader rejects incomplete or nonidentical
matched arms, the grader emits arm and pair outcomes, independent-review
declarations are required when selected by policy, and non-candidate usage can
be recorded without converting unknown counters to zero. Existing v1/v2
manifest hashes and grading behavior remain compatible.

## Review findings

The review exercised missing arms, cross-arm prompt drift, paired incomplete
results, reviewer/author identity conflicts, false independence declarations,
invalid overhead counters and unknown reasoning usage. It identified one
accounting gap: the first implementation preserved overhead but did not produce
a combined candidate-plus-overhead total. The final implementation adds
`total_recorded_usage` and `usage_complete`; any unknown contributor makes the
corresponding total unknown.

No unresolved correctness issue remained. Independence is a machine-checked
declaration, not external identity proof. The harness does not preregister v3
tasks, choose a baseline, invoke a model, establish representative sampling,
attach billing, or change Ryuk runtime routing.

## Verification

Fifteen focused pilot/harness tests passed. Full offline suite: 404 passed and 8
external integrations deselected. Ruff passed; Mypy passed across 110 sources;
compileall, `git diff --check`, and the repository credential-pattern scan
passed. A copied v2 run regraded 26/26 with its original gate intact; because it
has no overhead ledger, the new all-in `usage_complete` field correctly remains
false without changing its saved evidence.
