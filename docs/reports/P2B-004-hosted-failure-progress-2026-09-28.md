# P2B-004 hosted failure behavior — progress record

Date: 2026-09-28
Status: in progress; provider-side contracts incomplete

## Bounded contract

`scripts/probe_nvidia_hosted_failures.py` performs two non-disruptive checks for
each exact approved route:

1. Send an intentionally invalid `messages` value with a one-token output cap
   and wait at most 30 seconds for an HTTP validation response.
2. Start a streaming generation request and cancel the local client operation
   after at most two seconds.

The probe stores timestamps, elapsed time, HTTP status, coarse error-shape
presence and local cancellation state only. It never stores credentials,
headers, prompts, generated output, reasoning, response IDs, response/error
bodies or arbitrary provider error values. It explicitly represents provider
cancellation acknowledgment, execution termination and late-result status as
unknown when the API supplies no evidence.

No overload was deliberately induced. Creating provider load merely to obtain a
429/503 would conflict with the bounded, non-disruptive Developer Program scope.

## Results

The sanitized result is
`evidence/phase2b/p2b-004-hosted-failures-2026-09-28.json`.

- Both malformed requests produced `ReadTimeout` after approximately 30
  seconds. No HTTP status or error object was observed. Therefore the live API's
  validation response behavior remains unknown.
- Both streaming requests were cancelled locally after approximately two
  seconds, before response headers. This establishes that the client operation
  can be bounded and closed; it does not prove the provider accepted
  cancellation or stopped execution.
- There was no supported channel to observe a late result. Late-result behavior
  remains unknown.
- Earlier P2B-002/P2B-003 runs provide real 120-second and 300-second read
  timeout observations. They do not prove route unavailability.

## Review

The implementation review verified bounded concurrency, no automatic retry and
explicit unknown provider outcomes. It tightened sanitization from arbitrary
provider error type/code values to boolean presence flags, preventing opaque
upstream values from entering retained evidence. Unit tests cover allowlist
consistency, body-message exclusion, malformed metadata and invalid bounds.

P2B-004 remains `IN PROGRESS`. It has real timeout and local cancellation
evidence, but it lacks provider-confirmed cancellation, late-result behavior, a
real malformed response and a safely observed overload response. WF-012 and
P2B-006 remain gated. No retry, availability, billing or production claim is
made.
