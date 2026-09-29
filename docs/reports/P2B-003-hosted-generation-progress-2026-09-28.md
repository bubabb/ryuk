# P2B-003 hosted generation and safe-limit measurement — progress record

Date: 2026-09-28
Status: in progress; one profile has a tested safe point and two failed boundary observations

## Contract

`scripts/probe_nvidia_hosted_generation.py` issues one ordinary, non-streaming,
temperature-zero request concurrently to each approved model route. This run
used the same 41-character synthetic/public prompt, a 64-token output cap and a
300-second read timeout for each route.

The saved observation contains only timings, HTTP status, configured and
returned model IDs, finish reason, output presence/character count and numeric
usage. It excludes credentials, headers, prompt text, output text, reasoning,
response IDs, response bodies and provider error details. Sanitizer tests cover
successful content, failure bodies and malformed metadata types.

## Results

The immutable sanitized result is
`evidence/phase2b/p2b-003-hosted-generation-2026-09-28.json`.

| Model | Result | Elapsed | Returned identity | Usage |
| --- | --- | ---: | --- | --- |
| `moonshotai/kimi-k3` | read timeout; no response observed | 300.133 s | unavailable | unavailable |
| `deepseek-ai/deepseek-v4.1-flash` | HTTP 200, finish `stop`, non-empty output | 56.956 s | exact match | 38 prompt, 14 completion, 52 total tokens |

DeepSeek therefore has one empirically tested safe point at this request shape:
41 prompt characters and a 64-token requested output ceiling. The response used
14 completion tokens and contained five output characters. This does not prove
that 64 output tokens were generated or that a larger input/output limit is
safe.

Kimi has no positive ordinary-generation observation. The timeout does not prove
the route unavailable, and the request was not automatically retried.

A later Kimi-only diagnostic used NVIDIA's documented `reasoning_effort: low`,
temperature 1 and a larger 256-token cap. It also reached the 300-second read
timeout without response headers, identity or usage. See
`docs/reports/P2B-003-kimi-low-reasoning-followup-2026-09-28.md`.

### DeepSeek boundary follow-up

A bounded DeepSeek-only follow-up tested two larger request shapes concurrently,
with temperature zero, no streaming, no retry and a 300-second timeout. The
immutable sanitized record is
`evidence/phase2b/p2b-003-deepseek-limits-2026-09-28.json`.

| Case | Request shape | Result |
| --- | --- | --- |
| Larger input | 6,212 prompt characters, 1,024 synthetic padding words, 64-token output cap | Read timeout at 300.464 seconds; no response metadata |
| Longer output | 92 prompt characters, exactly 64 requested output words, 256-token cap | HTTP 200 at 278.248 seconds; exact model identity, `finish_reason: length`, 49 prompt and 256 completion tokens, but no user-visible content |

Neither case passed its deterministic output contract, so neither is a safe
operating point. In particular, HTTP 200 and token usage do not establish
successful generation when the returned message has no content. The result
records observed failure boundaries only; it does not establish a maximum
context or output limit. No Kimi request was made in this follow-up.

## Review

The implementation review found and fixed a direct-script import-path failure
before any provider request was made. It also tightened finish-reason and token
count normalization so malformed provider values cannot enter evidence, and
added a test preventing the two probe allowlists from silently diverging.

The boundary probe was reviewed with five focused tests covering evidence
redaction, exact output validation, identity mismatch, preregistered request
bounds and invalid timeouts. Its CLI returns failure unless every observation
passes the output contract; the live run therefore failed closed as intended.

P2B-003 remains `IN PROGRESS`: the evidence is reproducible and positive for one
small DeepSeek point, but the two larger DeepSeek points failed, Kimi ordinary
generation remains unverified, and maximum safe input/output behavior for both
profiles is unknown. This result is not a benchmark, throughput claim, cost
claim or production activation decision.
