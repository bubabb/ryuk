# Model allocation pilot v2 review

Date: 2026-09-25. Frozen manifest commit: `a251c5a`. Manifest baseline:
`27a9192`. All task inputs were synthetic. No Ryuk inference endpoint,
deployment, private repository or production service was used.

## Decision

Pilot v2 **passes its preregistered first-pass gate**: all 26 tasks completed
and passed, no task was invalid or unrun, no tool-use violation occurred, and
there were zero critical failures. No infrastructure retry was needed.

| Model | Planned | Passed | Failed | Wilson 95% interval |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 8 | 8 | 0 | 67.56–100% |
| GPT-6 Sol | 12 | 12 | 0 | 75.75–100% |
| GPT-6 Astra | 6 | 6 | 0 | 60.97–100% |
| **Overall** | **26** | **26** | **0** | **87.13–100%** |

The overall lower bound narrowly exceeds 87%, but this does **not** establish
87% population reliability. The tasks are a small, purposive synthetic sample;
v2 is largely a corrected rerun of v1, has no randomized representative
sampling or matched all-Astra arm, and model identity is requested rather than
independently verified. It supports only the bounded claim that the recorded
allocation passed this preregistered task set.

## Review of implementation correctness

The v2 manifest hash binds the overlay, inherited v1 manifest and resolved task
set. P02 returned the newly explicit integer counts. P20 passed the original
migration checks plus zero-row, duplicate-row and conflicting-version-row
assertions, including unchanged schema state after rejection. Completed code
responses P09–P20 were manually inspected, hash-bound, screened for prohibited
constructs, and run with their hidden assertions in isolated Python processes.
Architecture responses P21–P26 were checked against every preregistered
criterion. No `test_failure.txt` or infrastructure-attempt artifact exists.

The review found no material correctness defect in the pilot implementation or
recorded grading. The authoring/evaluation agent also performed the manual
review, so this is a separate review pass but not an independent external
audit. Review prompts, expected answers and hidden checks were not provided to
candidate turns.

## Recorded candidate usage

| Model | Calls | Input tokens | Cached input | Output tokens | Reasoning output |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 8 | 112,244 | 13,056 | 310 | 0 |
| GPT-6 Sol | 12 | 171,041 | 35,328 | 7,171 | 4,930 |
| GPT-6 Astra | 6 | 88,030 | 12,160 | 2,373 | 421 |
| **Total** | **26** | **371,315** | **60,544** | **9,854** | **5,351** |

These are candidate-call counters only. Setup, orchestration, grading, review
and human-equivalent review time remain unmeasured. Applicable billing and a
matched baseline are absent, so no cost or savings claim is supported.

## Evidence and follow-up

The immutable run is stored under `evals/model_allocation/runs/pilot-v2/` with
prompt, response, measurement, response-bound review and grade artifacts.
Running the local grader reproduces 26 passes and the gate decision.

Before using this as a population or savings claim, preregister a larger,
independently curated, stratified evaluation; add a matched baseline; keep
critical security/provenance failures as hard stops; and measure all candidate,
retry and review costs. Pilot success does not unblock CTX-003, Phase 2B, live
activation or production certification.
