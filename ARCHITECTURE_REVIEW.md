# Ryuk Project and Architecture Review

**Review date:** August 31, 2026
**Review scope:** Repository implementation, inference architecture, operational reliability, testing, and alignment with current inference-serving systems
**Repository state reviewed:** `main` at `158767e`

## Executive Summary

Ryuk has a sound mission and one particularly strong architectural principle: it owns its inference contract and isolates external inference systems behind adapters. This is the correct foundation for a vendor-independent orchestration platform.

The current implementation is, however, an early proof of concept rather than an intelligent inference orchestration system. It demonstrates engine registration, availability checks, preferred-engine selection, and fallback to a mock engine. It does not yet model the entities, constraints, failure semantics, or evidence required for reliable model and deployment selection.

Overall assessment:

| Area | Assessment |
| --- | --- |
| Product vision | Strong |
| Vendor-independent boundary | Strong direction |
| Current inference contract | Useful but too narrow |
| Router implementation | Early availability-based prototype |
| Reliability model | Insufficient for production |
| Tests and evaluation | Not established |
| Production readiness | Low |

The most important architectural refinement is to make a verified **model deployment**—not merely an engine name—the object that Ryuk evaluates and routes to.

## Repository State

The reviewed repository contains:

- A FastAPI application
- Ryuk-owned `InferenceRequest`, `InferenceResponse`, and `InferenceEngine` types
- An engine registry
- A basic availability/fallback router
- A working SGLang HTTP adapter using `/generate`
- A deterministic mock engine
- Empty placeholder modules for vLLM, TensorRT-LLM, Dynamo, and NIM
- No implemented test suite
- An empty `README.md`

At review time:

- `main` matched `origin/main` at commit `158767e`.
- `AGENTS.md` was present but untracked.
- Python compilation succeeded in the `ryuk-ai` Conda environment.
- The documented fallback flow succeeded: SGLang was unavailable, mock was available, and a request preferring SGLang fell back to mock.
- Tests could not run because the repository contains no tests and `pytest` is not installed in the environment.

## What Is Already Good

The following decisions should be preserved:

1. **Ryuk-owned interfaces.** External SDK and protocol types are not the core domain model.
2. **Adapter isolation.** Vendor-specific behavior belongs behind engine/deployment adapters.
3. **Async public contract.** Network and inference work is represented asynchronously.
4. **Configuration-driven registration.** Enabled systems are selected through configuration.
5. **Graceful local fallback.** An offline local SGLang endpoint does not crash the application.
6. **Control-plane/worker separation.** The architecture does not assume the Mac development host performs GPU inference.
7. **Separate model and engine selection.** The project vision correctly treats these as different decisions.
8. **Separate audit and evaluation concepts.** Inspection and acceptance policy should remain distinct.
9. **No foundational proprietary-provider dependency.** Optional proprietary adapters can remain replaceable.

## Findings

### 1. Model identity can be falsely attributed

**Severity: High**

The API accepts a caller-provided model name. The SGLang adapter does not send that model identifier to SGLang or verify which model the deployment serves. It copies the requested value into the normalized response.

Relevant code:

- `backend/inference/base.py:9`
- `backend/inference/engines/sglang.py:97`
- `backend/inference/engines/sglang.py:167`

A caller can request one model while the SGLang process serves another, and Ryuk will report that the requested model produced the answer.

**Recommendation:** Model identity should be resolved from a registered deployment and, where possible, verified using deployment metadata. The request may express a desired model or requirements, but it must not be the authoritative record of what executed.

### 2. Fallback does not cover generation failures

**Severity: High**

The router performs availability checks, selects one engine, and invokes it once. If an engine passes its health check and subsequently times out, becomes overloaded, returns malformed data, or fails generation, Ryuk does not attempt another eligible candidate.

Relevant code:

- `backend/inference/router.py:37`
- `backend/inference/router.py:69`

**Recommendation:** Introduce an execution policy that supports:

- End-to-end deadlines
- Per-attempt timeouts
- Typed and classified failures
- Safe same-deployment retry
- Failover to another deployment
- Attempt limits and retry budgets
- Cancellation propagation
- An auditable record of every attempt

### 3. The planned flat engine list does not reflect real serving architectures

**Severity: High architectural concern**

SGLang, vLLM, TensorRT-LLM, Dynamo, and NIM are not equivalent peer engines:

- SGLang, vLLM, and TensorRT-LLM are execution engines.
- Dynamo is a distributed inference runtime and serving layer that can use those engines.
- NIM is a packaged and managed serving product whose current LLM architecture uses vLLM, with newer configurations involving Dynamo-based distributed inference.

Representing all five as a flat `engine` enum will lose important topology and ownership information.

**Recommendation:** Represent an executable candidate as a composition such as:

```text
model artifact
  + execution engine
  + serving runtime
  + deployment configuration
  + hardware/compute pool
```

This prevents Ryuk from treating `Kimi + vLLM`, `Kimi + vLLM + Dynamo`, and `Kimi served through NIM` as identical systems.

### 4. Capabilities cannot belong solely to an engine class

**Severity: High architectural concern**

Capabilities such as structured output, speculative decoding, quantization, multimodality, context length, and distributed execution generally depend on an intersection of:

- Engine and exact version
- Model architecture
- Model artifact and quantization
- Hardware
- Deployment configuration
- Enabled plugins or backends
- Serving runtime
- Current runtime state

A universal boolean such as `engine.supports_structured_output` will often be inaccurate.

**Recommendation:** Introduce separate concepts such as:

- `ModelSpec`
- `ModelArtifact`
- `EngineAdapter`
- `EngineVersion`
- `ServingRuntime`
- `ComputePool`
- `Deployment`
- `CapabilityClaim`
- `ObservedRuntimeState`
- `RoutingRequirement`
- `ExecutionAttempt`

Capability evaluation should resolve the intersection for a specific deployment candidate.

### 5. The inference contract is too completion-specific

**Severity: Medium-High**

The current request supports a prompt, model name, token limit, temperature, and generic metadata. It cannot cleanly represent:

- Chat messages and system instructions
- Streaming
- Structured output schemas
- Tool definitions and tool calls
- Multimodal inputs
- Embeddings or reranking
- Stop conditions
- Log probabilities
- Seeds and determinism controls
- Reasoning controls
- Priority, deadlines, and cancellation
- Tenant, request, and trace context

**Recommendation:** Preserve a stable common envelope while adding typed task/input/output variants. Do not turn `metadata` into an unvalidated catch-all for core inference semantics.

### 6. Mock inference is enabled by default in all environments

**Severity: Medium-High**

`backend/config.py:41` defaults `mock_enabled` to `True` without enforcing a development or test environment.

This creates a dangerous production failure mode: if real deployments are unavailable, Ryuk could silently return fabricated mock output.

**Recommendation:** Refuse to register the mock adapter outside explicit development/test environments unless a separate, unmistakable override is provided. Responses should also carry a strongly typed provenance marker.

### 7. Health checks are sequential and performed on the request path

**Severity: Medium**

The router checks candidates sequentially. The engine-status endpoint also checks every engine sequentially. With multiple remote deployments, response latency can become the sum of their health-check timeouts.

Relevant code:

- `backend/inference/router.py:45`
- `backend/main.py:57`

**Recommendation:** Collect health and runtime signals asynchronously in the background, timestamp them, and route using a defined freshness policy. Direct probes should run concurrently under a global deadline with per-adapter exception isolation.

### 8. Error semantics are insufficient

**Severity: Medium**

Only an unknown engine and the absence of an available engine receive controlled API mappings. Timeouts, malformed responses, protocol errors, capacity failures, and other adapter errors are not classified.

**Recommendation:** Define typed failures such as:

- `DeploymentUnavailable`
- `UnsupportedRequest`
- `ModelNotServed`
- `CapacityExceeded`
- `InferenceTimeout`
- `UpstreamProtocolError`
- `GenerationFailed`
- `Cancelled`

Retry and rerouting policies should operate on these classifications without exposing sensitive upstream details.

### 9. There is no testing or evaluation foundation

**Severity: Medium**

The `tests/` directory is empty and `pytest` is not installed in the documented environment. Syntax compilation is useful but does not validate behavior.

The initial test suite should cover:

- Registry normalization and duplicate behavior
- Unknown preferred engines
- Availability fallback
- Generation-time failure and failover
- Timeouts and malformed upstream responses
- Model/deployment compatibility
- Mock restrictions by environment
- API validation and error mapping
- Concurrent health checks
- Adapter contract behavior
- Deterministic router-policy decisions

Longer term, Ryuk also needs routing evaluation datasets, decision-quality metrics, and replayable execution traces.

### 10. API validation and operational controls are minimal

**Severity: Medium**

The public request accepts unbounded prompt strings and does not constrain temperature or token limits. There are no request deadlines, authentication, rate limits, tenant boundaries, quotas, or payload-size policies.

These may be acceptable at prototype stage, but the API contract should not become stable before these operational requirements are designed.

### 11. The SGLang transport will not scale well as implemented

**Severity: Medium**

The SGLang adapter uses blocking `urllib` operations moved to worker threads. This works for a prototype but provides no connection pooling and weak cancellation behavior. Its generation timeout defaults to 120 seconds, while availability checks occur separately and can race with execution state.

**Recommendation:** Use a lifecycle-managed asynchronous transport with connection pooling, explicit connect/read/write/pool timeouts, response-size limits, cancellation, and structured protocol validation.

### 12. Registry construction is tightly coupled to global settings

**Severity: Low-Medium**

`build_engine_registry()` imports the global settings object, registers only SGLang and mock, contains duplicate imports, and includes unreachable placeholder code after an early return.

**Recommendation:** Pass settings or deployment definitions into a registry/deployment builder. Keep construction deterministic and easy to override in tests.

### 13. Repository engineering foundations are incomplete

**Severity: Low, but immediate**

- `README.md` is empty.
- Four engine modules are empty placeholders.
- `requirements.txt` is a full environment freeze rather than clearly separated direct and development dependencies.
- No CI, formatter, linter, type checker, package metadata, or compatibility policy is present.
- `.env.example` does not document the inference-engine settings already defined in `backend/config.py`.
- `AGENTS.md` is untracked.

The existing `.gitignore` correctly excludes `.env`, caches, virtual environments, `.DS_Store`, logs, and common IDE state.

## Architectural Recommendation

### Core domain model

Ryuk should distinguish between the following layers:

```text
Task
├── content and modality
├── quality/risk requirements
├── output contract
├── latency/cost constraints
└── execution policy

ModelSpec
├── model family and architecture
├── context and modality capabilities
└── expected task-quality characteristics

ModelArtifact
├── exact version/revision
├── tokenizer/template
├── quantization
└── storage and integrity identity

Deployment
├── model artifact
├── execution engine and version
├── serving runtime
├── compute pool/hardware
├── configuration
└── endpoint or local worker identity

RuntimeState
├── readiness and health
├── queue/load
├── latency and throughput
├── capacity
└── observed reliability
```

The router should filter and rank `Deployment` candidates, not generic engine names.

### Routing pipeline

Recommended control flow:

```text
Task
  -> typed requirements
  -> compatible model artifacts
  -> compatible deployments
  -> hard-constraint filtering
  -> policy/risk scoring
  -> execution plan
  -> one or more execution attempts
  -> normalized result and provenance
  -> audit
  -> evaluation
  -> accept, revise, verify, or reroute
```

Hard constraints should eliminate candidates before scoring. Examples include unsupported context size, missing structured-output support, incompatible hardware, unavailable model artifacts, or unacceptable data-residency boundaries.

Scoring should remain policy-driven and explainable rather than being hard-coded as one permanent weighted average.

### Responsibility boundary with serving runtimes

Ryuk should own:

- Task understanding and requirements
- Model/deployment eligibility
- Cross-deployment and cross-provider selection
- Risk, quality, cost, and policy decisions
- Attempt budgets and high-level failover
- Provenance, audit, evaluation, and acceptance

Serving runtimes such as Dynamo should own low-level concerns they are designed for:

- Worker discovery
- KV-cache-aware routing
- Prefill/decode placement
- Continuous batching
- GPU scheduling
- Worker-local load balancing
- High-speed KV transfer

Ryuk should consume runtime signals without duplicating the runtime's token-level scheduling logic.

## OpenAI-Compatible Protocol Policy

Ryuk is correct not to use OpenAI-compatible types as its universal internal contract. That principle should not become a blanket prohibition on using such protocols at external adapter boundaries.

For example, the documented public inference interface for current NIM LLM is OpenAI-compatible. Dynamo also exposes defined frontend serving APIs while providing deeper runtime integration paths. Using a product's supported interface inside a dedicated adapter does not compromise Ryuk's vendor independence when:

- The protocol is confined to the adapter.
- Ryuk-owned domain objects remain authoritative.
- Semantic differences and vendor extensions are preserved.
- Capability discovery does not assume all implementations behave identically.
- External SDK types do not leak into the core.

The correct rule is:

> Do not make an OpenAI-compatible API Ryuk's universal internal inference abstraction. Use the actual supported interface of each external system, then normalize it at the Ryuk boundary.

## Observability and Audit Requirements

Every generation should eventually produce a durable execution record containing at least:

- Ryuk request ID and trace ID
- Task classification and requirements version
- Router/policy version
- Eligible and rejected candidates with reasons
- Selected model artifact and deployment identity
- Engine/runtime versions
- Attempt sequence and failure classifications
- Timing breakdown, including queue, prefill, decode, and end-to-end latency when available
- Token and cost accounting
- Sampling and structured-output settings
- Output provenance
- Audit result
- Evaluation decision
- Retry, revision, verification, or reroute reason

This evidence is required for debugging, evaluating routing quality, enforcing policy, and improving the system safely.

## Security and Governance Considerations

Before production use, Ryuk will need explicit designs for:

- Authentication and authorization
- Tenant isolation
- Rate limits and quotas
- Secret management
- Data classification and residency
- Prompt and output retention
- Audit-log access and redaction
- Model and artifact integrity
- Deployment allowlists
- Tool-execution boundaries
- Abuse controls
- Supply-chain and dependency scanning

Provider and deployment credentials should remain outside request objects and logs.

## Recommended Development Sequence

### Phase 1: Engineering baseline

1. Add direct runtime and development dependency definitions.
2. Add unit tests, formatting, linting, static typing, and CI.
3. Populate the README with setup, architecture, and truthful implementation status.
4. Document all configuration in `.env.example`.

### Phase 2: Correctness and safety

1. Correct model/deployment identity handling.
2. Disable mock outside explicit development/test environments.
3. Add typed error semantics.
4. Add deadlines, timeouts, attempt records, and generation-time failover.
5. Add request validation and payload limits.

### Phase 3: Domain and capability model

1. Define `ModelSpec`, `ModelArtifact`, and `Deployment`.
2. Separate declared capabilities from observed runtime state.
3. Represent capability provenance and freshness.
4. Implement hard-constraint filtering with explainable rejection reasons.

### Phase 4: Request and response evolution

1. Introduce typed chat and completion requests.
2. Add streaming and cancellation.
3. Add structured-output contracts.
4. Add tool, multimodal, embedding, and reranking variants only as required.

### Phase 5: One production-quality adapter

Implement one real deployment adapter thoroughly—likely vLLM—using its current native asynchronous engine interface where the process boundary permits it. Keep heavy GPU dependencies optional so the control-plane backend remains importable on macOS.

The adapter should include:

- Explicit version compatibility
- Capability reporting
- Model/deployment identity
- Readiness and runtime state
- Streaming and cancellation behavior
- Protocol validation
- Typed failure conversion
- Contract and failure tests

### Phase 6: Distributed runtime modeling

Model Dynamo as a serving/runtime topology capable of hosting execution backends, not simply as another flat engine. Determine which routing responsibilities belong to Ryuk and which belong to Dynamo.

### Phase 7: Audit and evaluation

Add audit and evaluation only after execution provenance is trustworthy. Begin with explicit schemas and measurable decisions rather than free-form second-model critique alone.

## External Architecture References

The following primary documentation was checked during this review:

- [SGLang documentation](https://docs.sglang.ai/)
- [vLLM `AsyncLLM` API](https://docs.vllm.ai/en/latest/api/vllm/v1/engine/async_llm/)
- [NVIDIA Dynamo architecture](https://docs.nvidia.com/dynamo/dev/knowledge-base/concepts/architecture)
- [NVIDIA Dynamo overview](https://docs.nvidia.com/dynamo/dev/knowledge-base/overview)
- [NVIDIA NIM LLM architecture](https://docs.nvidia.com/nim/large-language-models/latest/reference/architecture.html)
- [NVIDIA NIM LLM API reference](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html)

These interfaces and architectures evolve quickly. Adapter implementation should pin a supported version range and be checked against current primary documentation at implementation time.

## Final Assessment

Ryuk's central thesis is promising: it should be an intelligent, auditable control plane over replaceable models, serving runtimes, inference engines, and compute environments.

The immediate risk is not that the code is too small. The risk is prematurely extending the current flat engine abstraction until it becomes difficult to represent real deployments correctly. Building additional adapters before fixing identity, topology, capabilities, execution attempts, and failure semantics would multiply that problem.

The best next milestone is a tested vertical slice in which Ryuk:

1. Resolves a requested task to verified deployment candidates.
2. Rejects incompatible candidates with explicit reasons.
3. Executes under a deadline with traceable attempts and failure handling.
4. Returns normalized output with truthful model and deployment provenance.

That milestone would turn the existing proof of concept into a credible foundation for intelligent routing, audit, and evaluation.
