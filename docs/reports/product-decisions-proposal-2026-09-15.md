# Product decisions: proposed first certification slice

Status update: owner approved offline-first work, synthetic/public inputs only,
no private repositories, and observed catalog identity. The live proposals below
remain unapproved. This document does not authorize
network calls, spending, private data disclosure, or deployment activation.

| Decision | Concrete proposal | Still needed |
| --- | --- | --- |
| DEC-001 hosting | Hosted-first NVIDIA catalog for the first certification run; controller remains local | Confirm hosted-first or identify self-hosted endpoints |
| DEC-002 models | Exact existing profiles: `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4-flash-0731`; no substitutions | Confirm these candidates |
| DEC-003 data | Synthetic/public test inputs only; no private repository, personal, credential, or customer data; retain sanitized metrics locally and omit model text from logs | Confirm data scope and retention period; approve any provider/residency constraints before live calls |
| DEC-004 access/budget | Use a locally managed secret reference; no secret values in this report or chat; no paid compute allocation | Endpoint/secret reference and explicit maximum spend are missing; current authorized spend is zero |
| DEC-005 identity | Catalog identity is observed, missing required revision is configured-only, response model must match; allow only a bounded certification experiment with these limits | Confirm whether observed evidence is sufficient for the experiment; production remains gated |
| DEC-006 benchmarks | Start with 20 synthetic exact-answer chat cases per model, concurrency 1, at most 1024 output tokens/request; require 100% matching identity and complete attempts, zero payload leakage, and at least 95% exact-answer success | Approve thresholds and token/time budget; select pinned coding repositories/tasks for a later quality benchmark |

The proposed 40-request smoke run does not establish coding quality, long-context
support, throughput, cancellation, tool use, or production reliability. Fault
injection and unsupported-capability checks must have separate bounded plans.
Provider usage/cost uncertainty must be resolved before requesting a monetary
budget can be enforced; a token limit alone is not a dollar cost guarantee.

Implementation can continue offline without these decisions. Live certification,
production eligibility, and dependent phase gates cannot be marked passed by
approving this proposal alone: the required real-system evidence still has to
be collected and reviewed.
