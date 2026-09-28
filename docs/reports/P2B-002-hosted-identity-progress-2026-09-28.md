# P2B-002 hosted identity verification — progress record

Date: 2026-09-28
Status: in progress; live evidence incomplete

## Bounded contract

The new `scripts/probe_nvidia_hosted_identity.py` probe is restricted to:

- one authenticated `GET /v1/models` request;
- one synthetic chat generation request for each exact approved route,
  `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4.1-flash`;
- deterministic temperature zero, non-streaming responses and at most eight
  requested output tokens; and
- sanitized observations containing timestamps, HTTP status, elapsed time,
  response-model agreement, response/choice presence, finish reason, usage-field
  presence and a coarse failure type.

The probe never records the credential, authorization or response headers,
prompt text, generated text, reasoning text, response identifiers, complete
response bodies or provider error details. Unit tests verify that content,
reasoning, response IDs and error messages are absent from observations.

## Interrupted live attempt

The authorized probe started with the protected `NVIDIA_API_KEY` present. The
controller restarted while the requests were pending and before the process
emitted a sanitized result. No durable result file was requested or created,
and no process survived the restart. Consequently, it is unknown which requests
reached or completed at the provider and no status, response identity, usage or
failure observation can be claimed from this attempt.

The calls were not automatically replayed. This preserves Ryuk's conservative
unknown-outcome rule and avoids treating an interrupted control-plane session
as evidence. The attempt consumed no known paid resource, but provider-side
usage is also unknown; the USD 0 paid-spend ceiling remains in force.

## Explicitly resumed live attempt

The owner then explicitly requested continuation from the interruption. One new
bounded probe was run and its sanitized result was saved as
`evidence/phase2b/p2b-002-hosted-identity-2026-09-28.json`.

- The authenticated catalog returned HTTP 200 in 84.455 ms and contained both
  exact approved model IDs.
- The Kimi K3 generation request produced no response before the 120-second
  read timeout. No status, response ID, model ID, choices, finish reason or
  usage fields were observed.
- The DeepSeek V4.1 Flash generation request likewise produced no response
  before the 120-second read timeout, with none of those response fields
  observed.
- The run made no automatic retry. Because neither generation response was
  received, provider-side execution and usage remain unknown.

These are timeout observations, not proof that either route is unavailable and
not permission to increase the timeout or retry automatically. No response or
error body was retained. A separately authorized P2B-003 measurement later
returned HTTP 200 and the exact configured response identity for DeepSeek V4.1
Flash. That closes the live response-identity portion for DeepSeek only; it does
not retroactively change this attempt's timeout result.

## Gate assessment

P2B-002 remains `IN PROGRESS`. The authenticated catalog/readiness portion was
reconfirmed and P2B-003 later observed matching DeepSeek response identity.
Kimi response identity and the required sanitized account/dashboard mapping are
still incomplete. No artifact, weight, tokenizer, runtime or hardware identity
is claimed.

P2B-003 through P2B-005 must not use the timed-out requests in this attempt as
positive contract evidence. P2B-006 and P2B-007 remain blocked by their recorded
prerequisites.
