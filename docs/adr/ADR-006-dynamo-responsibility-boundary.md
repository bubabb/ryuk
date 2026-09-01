# ADR-006: Dynamo Responsibility Boundary

- Status: Accepted for benchmark integration; production adoption on hold
- Date: 2026-08-31
- Pinned evaluation target: NVIDIA Dynamo 1.4.1

## Context

Dynamo is a distributed serving runtime, not another interchangeable model
engine. Its frontend, discovery plane, event plane, router, and workers jointly
own request execution. Dynamo 1.4.1 supports pinned vLLM 0.26.0, SGLang 0.5.16,
and TensorRT-LLM 1.3.0rc22 profiles on its documented Linux/NVIDIA matrix.

The local controller has no compatible NVIDIA runtime, so it cannot produce
honest performance evidence. A working adapter and benchmark gate are useful;
an adoption claim is not.

## Decision

Ryuk may register one whole Dynamo deployment as a candidate. Ryuk owns:

- task, quality, policy, cost, location, and deployment selection;
- deadlines and retry/failover between deployments;
- normalized results, provenance, and audit records.

Once selected, Dynamo exclusively owns:

- worker discovery and worker selection;
- KV-aware routing and cache-event processing;
- aggregated or disaggregated prefill/decode placement;
- intra-deployment load balancing and worker recovery.

Ryuk must not send worker IDs, prefill IDs, data-parallel ranks, busy thresholds,
or Dynamo routing extensions. It talks only to the deployment frontend. A
Dynamo-managed vLLM worker is not separately registered as a Ryuk candidate.

The frontend's documented HTTP protocol remains contained in `DynamoEngine`;
it does not become Ryuk's internal contract. The selected topology and runtime
version are immutable deployment provenance.

## Adoption gate

Production adoption remains **HOLD** until direct aggregated, Dynamo aggregated,
and (where supported) Dynamo disaggregated runs use the same model revision,
image digests, hardware, request corpus, concurrency, and sampling settings.
Record TTFT, inter-token latency, output throughput, KV reuse, failure rate,
recovery time, and operational complexity. `scripts/evaluate_serving_candidate.py`
requires at least 10% throughput gain, no more than 5% p95 TTFT regression, no
reliability regression, and measured recovery. Teams may tighten these workload
thresholds, but must not weaken them without a new ADR.

## Consequences

- Double routing is structurally prohibited.
- Dynamo can be evaluated without coupling Ryuk to a backend engine.
- No unmeasured claim is represented as a production capability.
- Dynamo 1.4.1 is an evaluation pin, not a promise to accept every 1.x release.

## Sources

- [Dynamo architecture](https://docs.nvidia.com/dynamo/dev/knowledge-base/concepts/architecture)
- [Dynamo compatibility](https://docs.nvidia.com/dynamo/dev/reference/compatibility)
- [Frontend configuration](https://docs.nvidia.com/dynamo/reference/components/frontend-configuration)
- [Health-check reference](https://docs.nvidia.com/dynamo/dev/observability/signals/health-checks)
