# P2B-004 Kimi asynchronous-contract review

Date: 2026-09-28
Status: fail-closed adapter handling implemented; live contract still incomplete

## Non-inference provider evidence

Official NVIDIA documentation observed on 2026-09-28 states that the Kimi K3
chat endpoint may return:

- HTTP 200 when invocation is fulfilled;
- HTTP 202 when a result is pending, with a `requestId` to poll;
- HTTP 422 for validation failure; or
- HTTP 500 for invocation failure.

The linked polling contract is authenticated
`GET https://integrate.api.nvidia.com/v1/status/{requestId}`, returning 200,
202, 422 or 500.

Sources:

- https://docs.api.nvidia.com/nim/re/reference/moonshotai-kimi-k3-infer
- https://docs.api.nvidia.com/nim/re/reference/moonshotai-kimi-k3-statuspolling

Every Ryuk Kimi attempt timed out before response headers. No HTTP 202 or
request ID was observed or retained, so none of those unknown provider
operations can be polled after the fact.

NVIDIA's official NGC status page reported NVIDIA Build as a partial outage,
but the listed incident was SMS verification being unavailable in China while
Cloud Functions was reported operational. This does not support an inference
outage claim and cannot explain Kimi's request-specific timeouts:
https://status.ngc.nvidia.com/

The available browser-control surface could not initialize in this environment,
so no authenticated dashboard/recent-request or sanitized account mapping was
collected. P2B-002's DEC-007 dashboard/account evidence remains incomplete.

## Adapter hardening

`ManagedHTTPInferenceEngine` previously treated every 2xx response as a normal
JSON result. A documented 202 body would then fail later as malformed choices,
which incorrectly hid the accepted/pending state and allowed the generic
protocol failure to fail over to another deployment.

The adapter now raises `AsynchronousResultPendingFailure` for every HTTP 202,
including empty or invalid-JSON bodies. Its stable contract is:

- code `asynchronous_result_pending`;
- HTTP-facing status 503;
- retry classification `NEVER`;
- sanitized context containing operation, HTTP status, request-ID presence and
  JSON-validity booleans only; and
- no automatic polling, failover or replay.

The existing bounded response reader still caps the body. Tests prove a real
request ID never enters the exception/context, a valid 202 is non-retryable,
and an empty 202 is still classified as pending rather than malformed JSON.

## Gate assessment

This change prevents unsafe duplicate execution if a future request receives
the documented pending response. It does not establish that a live 202 works,
does not reconcile a pending result after restart, and does not prove provider
cancellation or late-result behavior. P2B-004 remains `IN PROGRESS`; WF-012 and
P2B-006 remain gated.
