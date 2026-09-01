# Ryuk Research and Engineering Implementation Plan

**Revised:** August 31, 2026
**Source review:** `ARCHITECTURE_REVIEW.md`
**Purpose:** Turn Ryuk's current fallback prototype into a trustworthy, measurable, vendor-independent inference control plane.

## 1. Strategic Objective

Ryuk should select and govern a **model deployment**, not merely call an engine by name.

The target decision object is:

```text
Model artifact
  + execution engine and version
  + serving runtime and topology
  + compute pool and hardware
  + deployment configuration
  + current runtime state
```

The target control loop is:

```text
Task
  -> requirements
  -> eligible deployments
  -> hard-constraint filtering
  -> policy ranking
  -> bounded execution attempts
  -> normalized result and provenance
  -> audit
  -> evaluation
  -> accept, revise, verify, or reroute
```

This plan deliberately builds evidence, correctness, and replayability before adding many adapters or machine-learned routing.

## 2. Architecture Rules

1. Ryuk owns its task, request, result, error, provenance, and policy models.
2. Vendor protocols stay inside boundary adapters.
3. Using an OpenAI-compatible protocol at a product boundary is permitted when it is that product's supported interface; it must never become Ryuk's internal abstraction.
4. Model identity is derived from a registered or discovered deployment, never copied unverified from a request.
5. Static declarations, discovered facts, and observed runtime metrics remain separate.
6. Hard constraints eliminate candidates before ranking.
7. Every routing decision and execution attempt is reproducible from recorded inputs and versioned policy.
8. The macOS controller must not import CUDA or heavy GPU-engine packages.
9. SGLang, vLLM, and TensorRT-LLM are execution backends; Dynamo is a distributed serving runtime; NIM is a managed serving product. They are not a flat list of equivalent engines.
10. Ryuk must not duplicate worker-level scheduling, batching, or KV-aware routing already owned by a serving runtime.

## 3. Delivery Method

Each milestone must be a small vertical slice with:

- An architecture decision record when a durable boundary changes
- Unit and contract tests
- Negative and failure-path tests
- A migration note for changed schemas
- Observable acceptance criteria
- A final compilation, test, diff, and secret check

No milestone should depend on unavailable GPU infrastructure unless explicitly labeled as an integration or benchmark gate.

### Required Architecture Decision Records

| ADR | Decision |
| --- | --- |
| ADR-001 | Controller versus GPU-worker process boundary |
| ADR-002 | Deployment identity and model provenance |
| ADR-003 | Typed task/result envelope and versioning policy |
| ADR-004 | Retry, failover, deadline, and idempotency semantics |
| ADR-005 | Capability evidence and freshness model |
| ADR-006 | Dynamo responsibility boundary |
| ADR-007 | Persistence and retention of execution traces |
| ADR-008 | Audit/evaluation threat model and acceptance policy |

## 4. Stage A — Establish a Trusted Baseline

### Milestone A1: Repository and Test Foundation

**Goal:** Freeze the current known behavior before modifying it.

#### Work

1. Separate direct runtime dependencies from development dependencies.
2. Add `pytest`, `pytest-asyncio`, HTTP mocking, `ruff`, and `mypy`.
3. Add tests for registry behavior, preferred selection, offline SGLang fallback, mock normalization, unknown engines, no available engine, and FastAPI endpoints.
4. Add CI for compilation, linting, typing, and tests.
5. Populate `README.md` with truthful setup, architecture, and maturity status.
6. Document every current setting in `.env.example`.
7. Remove duplicate imports and unreachable registry code.
8. Add a versioned fixture representing the current API response.

#### Exit Gate

- CI is green.
- The current SGLang-to-mock fallback is tested.
- No behavior change is mixed into this milestone.

### Milestone A2: API Safety and Mock Containment

**Goal:** Prevent invalid requests and fake production output.

#### Work

1. Validate prompt length, token limits, temperature, and payload size.
2. Add explicit application environment types.
3. Permit mock registration only in development and test modes.
4. Fail startup on unsafe production configuration.
5. Add stable request IDs and propagate trace IDs.
6. Return a clear prototype/non-production marker from mock output.

#### Exit Gate

- Production mode cannot register mock accidentally.
- Invalid input is rejected before routing.
- Every request has a correlation identifier.

## 5. Stage B — Correct the Core Domain Before Expanding Adapters

### Milestone B1: Deployment Identity and Provenance

**Goal:** Make every execution claim truthful.

#### Research Gate

For SGLang, verify the supported model metadata, readiness, cancellation, metrics, and generation surfaces for the pinned server version. Record findings in ADR-002 and an adapter compatibility document.

#### Minimal Domain Types

```text
ModelRef
├── publisher
├── family
├── artifact_id
└── revision

DeploymentRef
├── deployment_id
├── model_ref
├── engine
├── engine_version
├── serving_runtime
└── endpoint/worker identity
```

#### Work

1. Add explicit SGLang and mock deployment configuration.
2. Register deployments instead of accepting arbitrary engine instances alone.
3. Keep a temporary compatibility view for existing engine endpoints.
4. Derive response provenance from the selected deployment.
5. Compare configured and discovered model identity where supported.
6. Treat identity mismatch as an unavailable or invalid deployment.

#### Exit Gate

- A request cannot cause Ryuk to falsely claim a different model executed.
- Every response contains a stable deployment ID and model revision status.
- Identity mismatch behavior is tested.

### Milestone B2: Minimal Typed Task and Result Envelope

**Goal:** Define a stable core without attempting every modality.

Initially support text completion, chat messages, non-streaming results, and typed generation configuration.

```text
InferenceTask
├── request_id
├── input: TextInput | ChatInput
├── generation
├── requirements
├── deadline
└── trace_context

InferenceResult
├── output
├── finish_reason
├── usage
├── model_provenance
├── deployment_provenance
├── attempts
└── timing
```

#### Work

1. Create versioned Pydantic API schemas and framework-independent domain types.
2. Define explicit optional-versus-unknown semantics for token usage and timing.
3. Define normalized finish reasons.
4. Preserve vendor extensions under a namespaced adapter field only.
5. Add compatibility translation for the current `prompt` endpoint.
6. Defer streaming, tools, multimodality, embeddings, and reranking.

#### Exit Gate

- Text and chat tasks round-trip through mock and SGLang-compatible paths.
- Core semantics do not depend on an OpenAI schema.
- API compatibility behavior is documented and tested.

## 6. Stage C — Make Execution Reliable and Auditable

### Milestone C1: Typed Failure Model

```text
InferenceFailure
├── ConfigurationFailure
├── IdentityMismatch
├── DeploymentUnavailable
├── UnsupportedTask
├── CapacityExceeded
├── DeadlineExceeded
├── UpstreamProtocolFailure
├── GenerationFailure
└── Cancelled
```

Each failure records a stable code, retry classification, safe public message, internal diagnostic context, deployment/attempt IDs, and original cause without secret leakage.

#### Exit Gate

- API error mapping is deterministic.
- Router policies use error classes rather than parsing strings.
- Sensitive upstream bodies are not exposed.

### Milestone C2: Deadlines, Attempts, and Generation-Time Failover

**Goal:** Bound work and recover from execution failures safely.

#### Work

1. Define an end-to-end monotonic deadline.
2. Allocate per-attempt budgets from remaining time.
3. Record an immutable `ExecutionAttempt` for every try.
4. Add bounded failover across eligible deployments.
5. Retry the same deployment only for explicitly safe transient failures.
6. Propagate cancellation where supported.
7. Add circuit-breaker input without implementing a distributed breaker yet.
8. Prevent retry storms with maximum attempts and backoff budgets.

#### Exit Gate

- A healthy-then-failing engine can fail over.
- Requests respect the deadline within documented cleanup tolerance.
- Attempt order and decisions are replayable in tests.

### Milestone C3: Async SGLang Adapter Hardening

1. Replace thread-wrapped `urllib` with a lifecycle-managed async transport.
2. Add pooling and separate connect/read/write/pool timeouts.
3. Validate response schemas and size limits.
4. Normalize finish reasons, usage, and timing.
5. Implement cancellation if supported by the pinned SGLang version.
6. Add simulated-server contract tests and optional real-server tests.
7. Record exact server and protocol compatibility.

#### Exit Gate

- Cancellation, timeout, invalid JSON, identity mismatch, and overload behavior are tested.
- No blocking network calls remain in the adapter.
- The fallback path still passes.

## 7. Stage D — Capability and Runtime Evidence

### Milestone D1: Minimal Capability Constraint Model

Begin only with routing-critical constraints: task kinds, served model identity, context capacity, structured output, streaming, required accelerators/topology, data-location policy, and production eligibility.

Each claim records:

```text
value
source: declared | configured | discovered | measured
scope
engine/runtime version
observed_at
expires_at
confidence
```

#### Work

1. Define `RoutingRequirements` separately from capabilities.
2. Implement deterministic hard-constraint filtering.
3. Return structured rejection reasons.
4. Add a fixture matrix of valid and invalid model/engine/hardware combinations.
5. Test unknown capability behavior; unknown must not silently mean supported.

#### Exit Gate

- Eligibility is deterministic and explainable.
- Unknown and false capabilities have distinct behavior.
- Scoring cannot override a failed hard constraint.

### Milestone D2: Runtime-State Collection

Track liveness, readiness, admission/capacity state, timestamp/freshness, load signals, and recent latency/error summaries.

#### Work

1. Collect state concurrently outside the request path.
2. Use bounded probes and adapter-specific readiness semantics.
3. Cache observations with a freshness policy and mark stale state.
4. Treat Prometheus metrics as observability input, not transactional truth.
5. Make status endpoints return cached state immediately.
6. Feed attempt outcomes into short-term deployment state.

#### Exit Gate

- One slow deployment cannot delay routing or status responses.
- Readiness is distinct from process liveness.
- Stale observations are visible and policy-controlled.

## 8. Stage E — Add a Second Backend Through a Worker Boundary

### Milestone E1: vLLM Architecture Spike

**Research questions:**

1. Which pinned vLLM release supports the target Kimi artifacts and NVIDIA hardware?
2. Should Ryuk use a worker wrapper around `AsyncLLM`, a standalone native service, or a Dynamo-managed backend?
3. How are cancellation, streaming, priority, LoRA, multimodality, and metrics exposed?
4. Which process owns tokenization and chat templates?
5. How can local tests avoid importing CUDA on the controller?

**Deliverables:** ADR-001, a compatibility matrix, a Linux/NVIDIA spike, benchmark measurements, and a go/no-go decision. No placeholder should be called implemented.

### Milestone E2: Production vLLM Worker Adapter

1. Implement the boundary selected in ADR-001.
2. Keep vLLM/CUDA dependencies in the GPU-worker environment.
3. Add generation, streaming groundwork, cancellation, identity, health, and metrics.
4. Normalize failures and provenance through Ryuk types.
5. Run the shared adapter contract suite.
6. Add Linux/NVIDIA integration tests and benchmark baselines.

#### Exit Gate

- The macOS controller works without vLLM or CUDA.
- SGLang and vLLM pass the same semantic contract suite.
- Ryuk can fail over between two truthful deployments.

## 9. Stage F — Explainable Policy Routing

### Milestone F1: Deterministic Policy Engine

Pipeline: resolve requirements, filter hard incompatibilities, rank eligible deployments with versioned rules, record an explanation, then execute under the attempt policy.

Initial ranking inputs:

- User policy preference
- Readiness and signal freshness
- Context headroom
- Recent failure rate
- Queue/capacity signal
- Static cost class
- Measured latency class
- Task-to-model suitability from curated evidence

Do not use a learned router or claimed accuracy score until a valid evaluation dataset exists.

Every decision records policy version, requirements, eligible/rejected candidates, signals and freshness, ranking, selection, and attempt plan.

### Milestone F2: Routing Evaluation Harness

1. Create a versioned task corpus with constraints and expected eligibility.
2. Add counterfactual replay where affordable.
3. Measure constraint violations, completion success, deadline success, cost per accepted result, latency, failover recovery, and decision stability.
4. Track coverage and uncertainty rather than fabricating accuracy.
5. Require an evaluation report for policy changes.

#### Exit Gate

- Router changes have measurable acceptance criteria.
- Performance and quality regressions can block release.

## 10. Stage G — Distributed Serving and Managed Products

### Milestone G1: Dynamo Integration Decision

**Implemented 2026-08-31:** ADR-006, a deployment-level controller adapter,
opt-in integration contract, and measured adoption gate are complete. Adoption
is on hold until the documented NVIDIA benchmark matrix supplies evidence.

Dynamo separates request, control, and event/state paths and can host vLLM, SGLang, and TensorRT-LLM. Ryuk must not reproduce its KV-aware routing or prefill/decode placement.

Benchmark representative workloads using direct aggregated execution, Dynamo aggregated execution, and Dynamo disaggregated execution where hardware permits. Compare TTFT, inter-token latency, throughput, KV reuse, operational complexity, and recovery.

Ryuk selects a Dynamo deployment using task, quality, cost, and policy constraints. Dynamo selects workers and manages KV-aware/disaggregated execution within it.

#### Exit Gate

- ADR-006 prevents double routing.
- Dynamo adoption is justified by measured workload benefit.

### Milestone G2: NIM Deployment Adapter

**Implemented 2026-08-31:** the standard-mode NIM LLM 2.0.11 profile is pinned;
the typed adapter, fail-closed provenance checks, registry configuration,
contract tests, and optional licensed integration test are complete.

1. Pin a supported NIM release/profile set.
2. Use documented readiness, metadata, model, inference, and metrics surfaces.
3. Keep the external protocol inside the adapter.
4. Record NIM, backend, model profile, and deployment provenance where discoverable.
5. Add contract tests and an optional licensed integration suite.

### Milestone G3: TensorRT-LLM Decision Gate

**Completed 2026-08-31 — HOLD:** current compatibility was verified, but this
workspace cannot produce comparable NVIDIA performance evidence. The benchmark
protocol and machine-readable decision gate are implemented; no adapter will be
built until the gate passes.

Do not implement TensorRT-LLM merely to complete a checklist. First identify a model/hardware/workload where it offers measurable advantage and verify compatibility against pinned versions. Proceed only after a benchmark spike and report.

## 11. Stage H — Advanced Task Contracts

**Implemented 2026-08-31:** semantic contracts, deterministic validation,
cancellation/stream events, tool-call representation, a bounded image slice,
and separate embedding/reranking families are covered by contract tests. No
deployment is marked capable without deployment-specific evidence.

Add one vertical slice at a time:

1. Streaming and cancellation end to end
2. Structured output with deterministic schema validation
3. Tool-call representation without tool execution
4. Multimodal input for one validated model/deployment combination
5. Embeddings or reranking as separate task/result types

Each feature requires a semantic definition, capability constraint, contract/API/failure tests, and evaluation fixtures. Never emulate unsupported capability in the router.

## 12. Stage I — Audit and Evaluation Intelligence

**Implemented 2026-08-31:** ADR-008, deterministic validation, structured model
audit evidence, bounded evaluation actions, and a labeled replay corpus are in
place. Production model-based audit remains gated by representative calibration.

### I1: Deterministic Validation

Start with schema, required-section, citation-format, length/language, policy, and secret-leakage checks.

### I2: Model-Based Audit

Define a structured `AuditReport` containing claims, evidence requirements, instruction failures, contradictions, uncertainty, and severity. Calibrate it on labeled fixtures.

### I3: Evaluation Policy

```text
accept
revise
regenerate
verify
reroute
escalate
```

Record auditor and generator identities, run deterministic checks first, strictly bound loops, support independent verification for high-risk tasks, measure audit errors, and include prompt injection in ADR-008's threat model.

#### Exit Gate

- Decisions are structured, bounded, and replayable.
- Audit adds measured value on a labeled evaluation set.

## 13. Stage J — Production Control Plane

**Implemented 2026-08-31 as a reference boundary:** ADR-007, authentication,
tenant authorization, quota/admission control, secret references, governance,
durable versioned records with backup, safe telemetry, artifact integrity, and
deployment lifecycle rules are implemented. Distributed rollout remains gated
by the external operational evidence listed in ADR-007.

Add authentication, tenant isolation, quotas, admission control, secret management, data governance, durable execution records, observability, deployment lifecycle APIs, artifact integrity, supply-chain scanning, load/soak/chaos tests, schema migration, backup, and disaster recovery after the execution model stabilizes.

## 14. Research and Benchmark Discipline

Every integration benchmark must record exact versions and image digests, model revision, quantization/template, GPU/interconnect/driver/CUDA details, parallel settings, workload distributions, concurrency, warmup, sample count, TTFT, inter-token and end-to-end latency, throughput, errors, memory/utilization, estimated cost, and untested features.

Results lacking this context must not become routing evidence.

## 15. First Production Slice and Non-Goals

The first production-capable slice succeeds when Ryuk safely routes text/chat tasks across two verified deployments, honors hard constraints and deadlines, fails over during execution, and returns complete provenance and attempt records.

It does not require a learned router, every engine, automatic deployment, multimodal routing, recursive audit loops, global scheduling, or a universal capability ontology.

## 16. Ordered Delivery Backlog

1. A1 — Repository and test foundation
2. A2 — API safety and mock containment
3. ADR-002 and B1 — Deployment identity and provenance
4. ADR-003 and B2 — Minimal task/result envelope
5. C1 — Typed failure model
6. ADR-004 and C2 — Deadlines, attempts, and failover
7. C3 — Async SGLang hardening
8. ADR-005 and D1 — Capability constraints
9. D2 — Runtime-state collection
10. ADR-001 and E1 — vLLM architecture spike
11. E2 — Production vLLM worker adapter
12. F1 — Deterministic policy engine
13. F2 — Routing evaluation harness
14. ADR-006 and G1 — Dynamo decision and integration
15. G2 — NIM deployment adapter
16. G3 — TensorRT-LLM decision gate
17. H — Advanced tasks
18. ADR-008 and I — Audit and evaluation
19. ADR-007 and J — Production control plane

## 17. Immediate Next Change Set

Start only with A1.

Expected changes: dependency/tooling files, `README.md`, `.env.example`, mechanical registry cleanup, tests, and CI configuration.

Required validation:

1. Compile all backend modules.
2. Run the complete test suite.
3. Run lint and static typing.
4. Exercise the SGLang-offline-to-mock fallback.
5. Inspect `git diff --check` and the complete diff.
6. Exclude secrets, `.env`, caches, and generated artifacts.

Do not begin domain changes until A1 is green.

## 18. Primary Technical References

- [SGLang documentation](https://docs.sglang.ai/)
- [vLLM AsyncLLM API](https://docs.vllm.ai/en/latest/api/vllm/v1/engine/async_llm/)
- [NVIDIA Dynamo overall architecture](https://docs.nvidia.com/dynamo/dev/knowledge-base/overview)
- [NVIDIA Dynamo compatibility matrix](https://docs.nvidia.com/dynamo/dev/reference/compatibility)
- [NVIDIA Dynamo vLLM backend](https://docs.nvidia.com/dynamo/dev/backends/v-llm/reference-guide)
- [NVIDIA Dynamo SGLang backend](https://docs.nvidia.com/dynamo/dev/backends/sg-lang/reference-guide)
- [NVIDIA NIM LLM architecture](https://docs.nvidia.com/nim/large-language-models/latest/reference/architecture.html)
- [NVIDIA NIM LLM API reference](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html)

Every implementation milestone must re-check current primary documentation, pin a supported version range, and record the result.
