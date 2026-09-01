# ADR-002: Deployment Identity and Model Provenance

- **Status:** Accepted for initial implementation
- **Date:** August 31, 2026
- **Owners:** Ryuk architecture
- **Related milestone:** B1

## Context

Ryuk currently accepts a caller-supplied `model` string, sends only the prompt
and sampling parameters to SGLang, and copies the requested model string into
the response. This can falsely attribute output to a model that the deployment
did not execute.

An engine name is also not a sufficient routing identity. Multiple deployments
can run the same engine with different model artifacts, versions, hardware,
serving runtimes, and operational state.

SGLang's current native server exposes `/model_info`, including `model_path`,
`served_model_name`, tokenizer path, weight version, model type, architectures,
and modality indicators. `/server_info` exposes resolved startup configuration,
live scheduler state, and the SGLang version, but it is a heavier operational
surface and has had version-specific blocking behavior.

## Decision

Ryuk will route to a registered `Deployment`, not accept an engine name as the
authoritative execution identity.

The initial identity types will be conceptually equivalent to:

```text
ModelRef
├── artifact_id
├── revision: optional
└── served_name: optional

DeploymentRef
├── deployment_id
├── model_ref
├── engine_name
├── engine_version: optional
├── serving_runtime: optional
└── endpoint identity
```

Configuration supplies the expected identity. Adapter discovery supplies the
observed identity. Ryuk compares them before marking a deployment ready.

Identity verification will use an explicit state:

```text
verified
configured_only
unverified
mismatch
```

- `verified`: configured and observed identity agree.
- `configured_only`: an operator supplied identity, but the adapter cannot
  currently discover enough information to verify it.
- `unverified`: neither configuration nor discovery establishes trustworthy
  model identity.
- `mismatch`: configured and observed identity conflict.

Production routing must reject `mismatch` and `unverified`. Whether
`configured_only` is eligible is an explicit environment/policy decision; it
must never be presented as verified.

The API request may express a desired model, but it does not determine the
reported executed model. Result provenance comes from the selected deployment
and its verification state.

## SGLang Discovery Policy

For the direct SGLang adapter:

1. Use bounded `GET /model_info` as the primary identity surface.
2. Read at least `model_path`, `served_model_name`, `weight_version`,
   `model_type`, and `architectures` when present.
3. Treat absent fields as unknown, not as a match.
4. Do not infer an immutable Hugging Face revision from a mutable model path.
5. Use bounded `GET /server_info` only for version/topology enrichment, not as
   the critical readiness probe.
6. Store raw vendor discovery data only in a namespaced adapter field.
7. Record discovery time and the supported SGLang compatibility profile.

The first compatibility target is the immutable SGLang `v0.5.18` release
profile documented on August 31, 2026. Ryuk will not assume compatibility with
mutable `latest`, `dev`, or unversioned `main` deployments. Actual GPU-worker
images must be pinned by immutable version tag and preferably image digest.

## Readiness Policy

Identity and readiness are separate:

- Identity answers what the deployment represents.
- Readiness answers whether it can currently accept the relevant task.

The existing `/health` probe can exercise scheduler communication and may be
more expensive than liveness. It must use a strict client-side timeout and must
not run sequentially across deployments on every user request in the eventual
runtime-state design.

Ryuk will initially preserve the current bounded health behavior, then move
probing into the runtime-state collector in Milestone D2.

## Cancellation Policy

SGLang supports request IDs and cancellation behavior, including cancellation
on client disconnect in current native serving paths. However, cancellation
semantics vary by topology and release, and recent upstream issues demonstrate
that HTTP success from an abort request is not sufficient proof that compute
stopped.

Therefore:

- Cancellation is not part of B1's identity implementation.
- It will be implemented and contract-tested during C3.
- Cancellation support will be a deployment capability with version/topology
  scope, not a universal engine boolean.
- Ryuk will treat cancellation acknowledgement separately from confirmed
  termination when the upstream interface cannot prove termination.

## Consequences

### Positive

- Responses can no longer truthfully depend on caller-controlled model labels.
- Multiple deployments of one engine become distinguishable.
- Weight updates and version changes can invalidate identity observations.
- Future SGLang, vLLM, Dynamo, and NIM integrations share a Ryuk-owned concept
  without pretending their discovery surfaces are identical.

### Costs

- Registry and router APIs must migrate from engine instances to deployments.
- Availability checks will eventually need cached discovery/runtime state.
- Configuration requires stable deployment and expected-model identifiers.
- Older SGLang servers may provide weaker identity and remain
  `configured_only` or ineligible.

## Rejected Alternatives

### Trust the request's model string

Rejected because it can produce false provenance.

### Use the engine name as deployment identity

Rejected because one engine can host many independent deployments and model
artifacts.

### Require one universal discovery endpoint

Rejected because external systems expose materially different supported
management surfaces.

### Treat model path as an immutable revision

Rejected because aliases, local paths, and mutable repositories do not prove
artifact immutability.

## Implementation Follow-Up

1. Add `ModelRef`, `DeploymentRef`, and identity-verification types.
2. Add explicit SGLang and mock deployment settings.
3. Build a deployment registry while preserving a temporary engine view.
4. Add bounded SGLang `/model_info` discovery.
5. Reject identity mismatch before generation.
6. Return deployment-derived provenance from the API.
7. Add mismatch, unknown, timeout, and older-server contract tests.

## Primary References

- [SGLang HTTP server source](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/entrypoints/http_server.py)
- [SGLang installation and immutable image guidance](https://docs.sglang.ai/get_started/install.html)
- [SGLang releases](https://github.com/sgl-project/sglang/releases)
- [Dynamo SGLang backend reference](https://docs.nvidia.com/dynamo/dev/backends/sg-lang/reference-guide)
