# P2B-003 hosted generation and safe-limit measurement — progress record

Date: 2026-09-28
Status: in progress; one profile has a tested safe point

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

## Review

The implementation review found and fixed a direct-script import-path failure
before any provider request was made. It also tightened finish-reason and token
count normalization so malformed provider values cannot enter evidence, and
added a test preventing the two probe allowlists from silently diverging.

P2B-003 remains `IN PROGRESS`: the evidence is reproducible and positive for one
bounded DeepSeek point, but Kimi ordinary generation and maximum safe
input/output behavior for both profiles remain unverified. This result is not a
benchmark, throughput claim, cost claim or production activation decision.
