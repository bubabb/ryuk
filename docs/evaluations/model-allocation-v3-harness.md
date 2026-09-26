# Model allocation v3 harness contract

Date: 2026-09-25  
Status: implemented; no v3 benchmark or model run is preregistered

The v3 harness extends the existing immutable-manifest runner and local grader
without changing pilot v1 or v2 evidence. It is infrastructure for a future
larger evaluation, not the evaluation itself.

## Matched comparison manifests

A manifest may declare `comparison.arms`, a `baseline_arm`, and
`require_complete_pairs`. Every task must then include a nonblank `case_id` and
one declared `arm`. Each case must occur exactly once in every arm. Prompt,
expected answer, hidden checks, criticality and category must be identical
across a case's arms; only assignment fields such as ID, model and effort may
differ. Invalid or unmatched manifests are rejected before calls.

The grader reports each arm and paired pass/fail combinations. An ungraded
member makes its pair incomplete rather than silently removing it.

## Independent review declaration

A future manifest can set `review.require_independent` to true. Its review file
must include `_meta` with a nonblank `reviewer_id`, nonempty
`candidate_author_ids`, and `independent: true`; the reviewer ID cannot appear
among candidate authors. This makes the declaration explicit and mechanically
enforced, but cannot prove real-world identity or independence by itself.

## Non-candidate usage

The grader accepts `--overhead path/to/overhead.json`. The file maps named
categories such as setup, grading and review to all four token counters:
`input_tokens`, `cached_input_tokens`, `output_tokens`, and
`reasoning_output_tokens`. Values are nonnegative integers or `null`; missing
fields are rejected. The summary preserves the ledger, calculates an all-in
total, and makes a total field `null` if any contributing value is unknown.
`usage_complete` is true only when every total is known.

This prevents absent reviewer/setup telemetry from being counted as zero. A
savings claim still requires applicable billing, comparable quality and a
preregistered representative sample.
