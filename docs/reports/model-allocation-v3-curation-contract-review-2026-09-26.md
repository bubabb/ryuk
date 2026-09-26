# Model-allocation v3 curation-contract review

Date: 2026-09-26  
Scope: EVAL-007, offline contracts only

## Outcome

Accepted. The case-centric schema, validator, deterministic compiler, and
curation packet preserve the frozen v3 design without creating evaluation
cases or authorizing a run.

The validator requires 100 unique, content-addressed synthetic/public cases in
the exact five preregistered strata. It records independent-curator and holdout
attestations, permits exactly one hidden grading mode, freezes the allocation
model/effort, and rejects unknown fields. The compiler expands each case into
allocation and all-Astra/high tasks and then applies the existing matched-arm
validator. Candidate prompts continue to exclude grading material.

## Integration review

- Matched validation now binds prompt, grading, criticality, category, stratum,
  and source provenance across arms.
- Declared prose-review criteria work for every allocation model. Check-based
  code cases enter the same restricted Python-check path in both arms,
  including the Astra baseline; the legacy v1/v2 Astra convention is preserved.
- The v3 overall quality decision now requires 94 allocation passes, complete
  graded pairs, zero critical failures, and a passing paired noninferiority
  interval. The legacy aggregate pilot gate cannot supersede these conditions.
- Generated test fixtures exercise all 100 cases entirely in memory or under
  temporary paths. They are explicitly not a real curation manifest.

## Remaining boundaries

No case content, sampling frame, real curator/reviewer identity, billing
snapshot, model-access probe, owner approval, candidate response, or provider
call was produced. Attestations remain declarations requiring independent
evidence. Governance remains blocked, and this review makes no reliability,
savings, availability, or production-readiness claim.

Final verification: 444 offline tests passed and 8 external integrations were
deselected. Ruff, Mypy across 116 sources, compileall, schema JSON parsing,
`git diff --check`, and the repository credential-pattern scan passed.
