# Model-allocation v3 review and savings contract review

Date: 2026-09-26  
Scope: EVAL-008, offline evidence contracts only

## Outcome

Accepted. The blinded-review and all-in savings contracts are hash-bound,
complete-by-construction, and fail closed. No real evidence or model activity
was introduced.

The review ledger binds the resolved manifest, raw run metadata, the complete
response set, opaque alias map, every review-required task, and every reviewed
response. It requires an
independent reviewer, exact candidate-author agreement with the manifest, arm
labels hidden through score freeze, and a strictly later unblinding timestamp.
The finalized ledger can be converted to the existing grader input only after
validation.

The savings ledger binds the manifest, run, finalized review ledger, and the
governance billing snapshot. It requires applicable USD rates for every used
model, complete candidate counters, and setup/grading/review counters for both
arms. Costs are recomputed with cached input separated from uncached input;
reasoning tokens are declared included in output and are not double billed.

## Gate review

- Unknown, negative, malformed, incomplete, unpriced, or inconsistently cached
  usage is rejected instead of treated as zero.
- Savings cannot pass unless the complete matched quality gate passed first.
- The baseline all-in cost must be positive, and the recomputed reduction must
  meet the frozen 25% threshold.
- V3 grading rejects loose legacy overhead, requires both evidence ledgers, and
  checks reviewer and billing IDs against ready governance.
- Legacy v1/v2 review and overhead formats remain unchanged.

## Remaining boundaries

The schemas and tests contain synthetic fixtures only. No reviewer or candidate
identity, response, usage measurement, rate, billing snapshot, access probe,
owner approval, provider call, or spend was recorded. Declarations do not prove
independence or billing applicability. Governance remains blocked, and no
reliability or savings claim is supported.

Final verification: 459 offline tests passed and 8 external integrations were
deselected. Ruff, Mypy across 118 sources, compileall, both schema JSON parses,
`git diff --check`, and the repository credential-pattern scan passed.
