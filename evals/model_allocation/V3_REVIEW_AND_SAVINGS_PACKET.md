# V3 blinded review and savings evidence packet

Status: contract template only. It records no reviewer identity, response,
billing snapshot, usage measurement, approval, or model call.

## Blinded review sequence

1. After the run is immutable, assign opaque `B001`–`B200` identifiers using a
   map whose canonical SHA-256 is recorded. Give the independent reviewer only
   blind IDs, candidate content, source hashes, and grading material—not task
   IDs, arm labels, models, or usage/cost data.
   Canonicalization is the ordered array of `blind_id`/`task_id` objects encoded
   as UTF-8 JSON with sorted keys and separators `,` and `:`.
2. Freeze every required verdict and note, record the timezone-aware freeze
   timestamp, then unblind. Unblinding must not precede frozen scores.
3. Add the task IDs to the finalized ledger without changing verdicts. Bind the
   ledger to the resolved manifest, raw `run.json`, every response artifact,
   and individual reviewed-response hashes. The complete response-set digest is
   the canonical task-ID-sorted array of `task_id`/`response_sha256` objects,
   encoded with the same JSON rules as the alias map.
4. Validate against `v3-review-ledger.schema.json`. The grader additionally
   checks exact task coverage, alias-map integrity, reviewer independence, and
   response hashes. Invalid tasks remain explicit and fail completeness.

## All-in savings sequence

1. Record an applicable billing snapshot with stable source reference and USD
   per-million-token rates for every candidate and overhead model. Never infer
   missing rates or treat unknown usage as zero.
2. Record setup, grading, and review token usage separately for both arms. Each
   record names its model. Cached input must not exceed total input.
3. Bind the savings ledger to the manifest, raw run, and finalized review-ledger
   hashes and to the billing snapshot ID in governance.
4. Validate against `v3-savings-evidence.schema.json`. The grader recomputes
   candidate and overhead costs. Reasoning tokens are treated as included in
   output tokens and are not billed twice.
5. Evaluate savings only after the complete quality gate passes. The required
   reduction is at least 25% versus the all-Astra/high arm's all-in cost.

## Fail-closed checklist

- [ ] Reviewer differs from every candidate author and matches governance.
- [ ] All review-required responses were scored while arm/model labels hidden.
- [ ] Scores were frozen before the recorded unblinding time.
- [ ] Alias, manifest, run, review, response, and billing bindings match.
- [ ] Every candidate call has all four nonnegative token counters.
- [ ] Both arms have setup, grading, and review usage records.
- [ ] Every used model has an applicable nonnegative decimal rate.
- [ ] Quality passed before savings was considered.
- [ ] Baseline all-in cost is positive and reduction is at least 25%.

Declarations and identifiers do not prove real independence, billing
applicability, or model access. If evidence is missing or disputed, keep the
savings decision false and governance blocked.
