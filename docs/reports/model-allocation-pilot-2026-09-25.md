# Model allocation pilot v1 review

Date: 2026-09-25. Repository baseline: `32adfd1`. All task inputs were
synthetic. No Ryuk provider endpoint or deployment was used.

## Result

The preregistered pilot had 26 bounded tasks: 8 Luna, 12 Sol and 6 Astra. There
are 24 valid, gradeable responses, one under-specified task and one
infrastructure failure. Of the 24 valid responses, 23 passed (95.83%). The
Wilson 95% interval is 79.76–99.26%. The pilot **fails its gate**: it has a
critical first-pass failure and is incomplete. The 87% population target remains
unverified.

| Model | Planned | Pass | Fail | Invalid or unrun | Gradeable observed rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 8 | 7 | 0 | 1 invalid | 100% (7/7) |
| GPT-6 Sol | 12 | 11 | 1 | 0 | 91.67% (11/12) |
| GPT-6 Astra | 6 | 5 | 0 | 1 infrastructure error | 100% (5/5) |

Luna P02 returned `offline_passed: true`; the key expected `359`. The prompt did
not specify whether this field was a count or boolean, so P02 is an invalid
measurement, not a model failure. Sol P20 missed the explicit requirement to
verify exactly one migration version row. This is a critical first-pass failure.
Astra P21 exited with a CLI infrastructure error after about three seconds and
produced no answer or usage data. An unscored Astra connectivity probe later
passed; P21 was not retried and remains unscored.

The evaluator applied a second reviewer pass to the preregistered criteria.
Code responses also ran locally against hidden assertions after source review.
The evaluator authored this benchmark and reviewed the candidates; this is not
an external independent audit. The tasks form a small purposive synthetic
sample, not a random sample of production tickets. There was no all-Astra
comparison arm.

## Recorded usage

Successful CLI turns, including the invalid P02 response:

| Model | Calls | Input tokens | Cached input | Output tokens | Reasoning output |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 8 | 112,240 | 39,168 | 366 | 56 |
| GPT-6 Sol | 12 | 170,994 | 47,104 | 6,688 | 4,578 |
| GPT-6 Astra | 5 | 73,354 | 0 | 1,895 | 351 |

P21 consumption, setup/reviewer tokens, human review time, applicable billing
terms and comparable baseline usage are unknown. These records do not establish
cost savings. Per-task prompt hashes, answers and measurements are saved under
`evals/model_allocation/runs/pilot-v1/`.

## Follow-up

Keep v1 unchanged. A new preregistered version should specify the P02 field type,
test missing/duplicate schema-version rows, and state how to resume after CLI
infrastructure failures without retrying scored quality failures. Increase the
sample and stratify by task type before making an 87% reliability statement.
Any authorization, tenant-isolation or replay failure remains a hard stop,
regardless of aggregate accuracy. Measure matched baseline quality and all
inference, review and retry costs before estimating savings.
