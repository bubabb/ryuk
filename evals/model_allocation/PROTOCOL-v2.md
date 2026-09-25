# Model allocation pilot v2 — preregistration

Date: 2026-09-25. Repository baseline: `27a9192`. This protocol is frozen
before any v2 candidate response. It inherits the 26 task definitions and
grading rules from v1 through the explicit, hash-bound overlay in
`pilot-v2.json`. Pilot v1 and its recorded results remain unchanged.

V2 corrects two measurement defects found in v1:

- P02 now names `offline_passed_count` and `deselected_count` and explicitly
  requires integer values. A boolean cannot satisfy either field.
- P20 now requires exactly one schema-version row before mutation and adds
  hidden zero-row, duplicate-row and conflicting-version-row assertions. Every
  invalid cardinality must leave the database unchanged and outside a
  transaction.

The first-pass gate remains 23 of 26, all tasks graded, no invalid tasks and no
critical failure. The same small, purposive sample still cannot establish 87%
population reliability or savings, even if the gate passes. Increasing and
independently curating a task set, adding a matched baseline arm, and measuring
all candidate/reviewer/retry usage remain separate prerequisites for such a
claim.

## Infrastructure continuation rule

The runner stops at an infrastructure error or timeout. `--resume` may rerun
only the interrupted task, only when its recorded status is one of the two
declared infrastructure statuses, and at most once. The original measurement
is preserved under that task's `infrastructure_attempts/` directory before the
continuation. Completed responses are never rerun. A wrong, unsafe, or
otherwise failed completed response is a scored first-pass quality failure and
is never eligible for resume.

The resolved manifest hash covers the v2 overlay, inherited v1 manifest and
fully resolved task set. The grader requires that exact hash. Model/provider
calls remain opt-in; preregistration and local tests do not execute them.

Prepared invocation, not authorized or executed by this change set:

```text
python scripts/evaluate_model_allocation.py \
  --manifest evals/model_allocation/pilot-v2.json \
  --output evals/model_allocation/runs/pilot-v2
```
