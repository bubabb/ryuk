# P2B-003 Kimi low-reasoning follow-up

Date: 2026-09-28
Status: completed diagnostic; P2B-002/P2B-003 gates remain open

## Reason for the follow-up

The initial Kimi requests omitted `reasoning_effort`. NVIDIA's current Kimi K3
endpoint reference states that reasoning is always enabled, the default effort
is `max`, and `low`, `high` and `max` are supported. It also recommends
temperature 1. This created a plausible, testable explanation for the repeated
timeouts without authorizing arbitrary retries.

Official reference observed on 2026-09-28:
https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-infer

## Bounded test

The generation probe was extended to select an exact subset of approved models,
record temperature and Kimi reasoning effort, and add `reasoning_effort` only to
Kimi requests. Mock-transport tests prove the field is included for Kimi and
excluded from DeepSeek.

One Kimi-only request used:

- `reasoning_effort: low`;
- temperature 1;
- a 256-token output cap;
- a 41-character synthetic/public prompt;
- non-streaming mode; and
- a 300-second read timeout.

The sanitized evidence is
`evidence/phase2b/p2b-003-kimi-low-generation-2026-09-28.json`.

## Result and decision

The request reached `ReadTimeout` after 300.189 seconds. No response headers,
HTTP status, response model, output or usage were observed. Provider-side
execution and usage remain unknown. The request was not retried.

This result weakens the hypothesis that default `max` reasoning alone caused
the earlier Kimi timeouts. It does not prove that Kimi is unavailable. Another
inference attempt is not justified until the account/dashboard or provider can
confirm route readiness, entitlement, queue behavior and any asynchronous
contract specific to this model.

The planned Kimi structured-output and tool-call follow-ups were not launched.
Ordinary generation remains unstable, so advanced capability calls would add
unknown provider execution without establishing the prerequisite contract.

P2B-002 and P2B-003 remain `IN PROGRESS`; P2B-005's Kimi cases remain
unverified. P2B-006 stays blocked.
