# SGLang Direct Adapter Compatibility Profile

**Research date:** August 31, 2026
**Initial target:** SGLang `v0.5.18`
**Ryuk integration status:** C3 direct-adapter contract implemented and covered
with simulated async-transport tests. Real-GPU validation remains required.

## Deployment Requirement

Use an immutable SGLang release image tag and preferably an image digest. Do not
use mutable `latest` or `dev` tags for a production deployment.

The direct adapter assumes the SGLang native HTTP server rather than the SGLang
Model Gateway or a Dynamo frontend. Gateway and Dynamo topologies require their
own deployment profiles because readiness, routing, cancellation, metrics, and
identity ownership differ.

## Native Surfaces

| Concern | Direct SGLang surface | Ryuk treatment |
| --- | --- | --- |
| Generation | `POST /generate` | Async native adapter with bounded schema validation |
| Model identity | `GET /model_info` | Primary discovery surface for B1 |
| Server version/topology | `GET /server_info` | Optional enrichment with strict timeout |
| Readiness | `GET /health` | Bounded probe; later collected outside request path |
| Load | `GET /v1/loads` | Future runtime-state input |
| Metrics | Prometheus metrics when enabled | Future observational input |
| Cancellation | Request ID/client disconnect and abort surfaces | Deferred to C3 contract tests |

Deprecated aliases such as `/get_model_info`, `/get_server_info`, and
`/get_load` must not be the primary implementation target.

## `/model_info` Fields of Interest

Current upstream source exposes fields including:

- `model_path`
- `served_model_name`
- `tokenizer_path`
- `is_generation`
- `preferred_sampling_params`
- `weight_version`
- `load_format`
- `reasoning_parser`
- `tool_call_parser`
- `has_image_understanding`
- `has_audio_understanding`
- `model_type`
- `architectures`

Ryuk must tolerate additive fields and absent optional fields. A successful HTTP
response with malformed required identity data is a protocol failure, not a
verified identity.

## Identity Comparison

The first comparison policy is intentionally conservative:

1. Compare configured expected artifact/model path with observed `model_path`
   when both exist.
2. Compare configured served name with observed `served_model_name` when both
   exist.
3. Compare configured revision with observed `weight_version` only when the
   deployment contract explicitly defines them as the same identifier.
4. Never derive an immutable revision from an alias or path string.
5. Any direct conflict yields `mismatch`.
6. Missing evidence yields `configured_only` or `unverified`, never `verified`.

Normalization must be limited to documented equivalences. Ryuk should not
silently treat arbitrary local paths and repository IDs as equal.

## Readiness Notes

Current SGLang health behavior can exercise the scheduler through a minimal
request. This is stronger and more expensive than process liveness. Ryuk must:

- Use a strict client timeout shorter than the overall routing deadline.
- Avoid sequential probes across deployments.
- Distinguish timeout, non-2xx status, malformed response, and identity mismatch.
- Cache runtime observations in the later D2 runtime-state collector.
- Avoid assuming a 200 response proves sufficient capacity for a large request.

## Cancellation Notes

Cancellation must be tested for each supported release and topology. Direct
server, SGLang Model Gateway, and Dynamo-managed SGLang do not necessarily have
identical behavior. Recent upstream reports show that abort acknowledgement can
precede or fail to prove actual termination in some paths.

Ryuk will expose cancellation only after tests demonstrate:

- A stable request ID reaches the server.
- Client cancellation reaches the correct worker or gateway.
- The generation stream terminates within a bounded interval.
- The deployment remains usable afterward.
- Unsupported disaggregated or LoRA cases are declared explicitly.

In C3, cancelling Ryuk's async operation closes the active HTTP response and
propagates cancellation through the transport. Ryuk does not claim remote worker
termination because the target release/topology has not passed a real-server
abort test. The stable Ryuk request ID is sent as SGLang's `rid` for correlation.

## Metrics and Runtime State

Metrics are observations rather than authoritative transaction state. When
enabled, use them for historical latency, throughput, queue, and error signals.
Do not decide that an individual request succeeded or terminated solely from a
Prometheus sample.

Under Dynamo, SGLang and Dynamo metrics may be exposed together on the Dynamo
system port. That topology belongs to a Dynamo deployment profile rather than
this direct-server profile.

## Compatibility Test Matrix for C3

The default suite uses an in-memory async HTTP transport. Set
`SGLANG_TEST_BASE_URL` to opt into the real-server health and identity contract
test against the pinned deployment; GPU generation/cancellation certification
remains deployment-specific.

| Case | Required result |
| --- | --- |
| Expected and observed identity match | Deployment may become ready |
| Model path or served name conflicts | `IdentityMismatch` |
| `/model_info` times out | Unavailable/unverified observation |
| `/model_info` returns malformed JSON | `UpstreamProtocolFailure` |
| Optional fields absent | Preserve unknown values safely |
| `/server_info` unavailable | Identity can still use `/model_info`; version remains unknown |
| `/generate` returns invalid JSON | `UpstreamProtocolFailure` |
| Generation exceeds deadline | `DeadlineExceeded` and cancellation attempt where supported |
| Client disconnects | Bounded cancellation behavior |
| Server is healthy after failed request | Subsequent request succeeds |

## Open Questions Before GPU Integration

1. Which exact Kimi artifact and revision is the first target?
2. Is `weight_version` controlled as an immutable artifact revision in Ryuk's
   deployment procedure?
3. Will the first worker be direct SGLang, SGLang Model Gateway, or Dynamo-managed?
4. Which GPU generation, count, interconnect, CUDA, and container digest will be
   used?
5. Which cancellation cases are required for the first production slice?

## Primary References

- [SGLang HTTP server source](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/entrypoints/http_server.py)
- [SGLang installation documentation](https://docs.sglang.ai/get_started/install.html)
- [SGLang release history](https://github.com/sgl-project/sglang/releases)
- [Dynamo SGLang backend reference](https://docs.nvidia.com/dynamo/dev/backends/sg-lang/reference-guide)
