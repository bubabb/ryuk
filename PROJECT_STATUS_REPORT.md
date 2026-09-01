# Ryuk Implementation Status, Open Items, and Next Steps

**Report date:** August 31, 2026
**Repository:** `/Users/bubagv/Desktop/projects/ryuk`
**Scope:** Work completed from the original architecture review through Stages
A–J, current verification evidence, known limitations, production blockers, and
recommended next work.

## 1. Executive Summary

Ryuk has progressed from an early availability-based inference prototype into a
vendor-independent inference control-plane foundation with:

- Ryuk-owned task, result, deployment, provenance, failure, routing, audit, and
  control-plane contracts;
- deterministic deployment eligibility and explainable routing;
- bounded execution with deadlines, attempts, cancellation classification, and
  generation-time failover;
- hardened SGLang, vLLM worker, Dynamo deployment, and NVIDIA NIM adapter
  boundaries;
- cached runtime-state collection;
- versioned routing and audit evaluation harnesses;
- advanced task semantics for streaming, structured output, tool calls,
  multimodal input, embeddings, and reranking;
- deterministic audit and bounded evaluation policy;
- reference production-control primitives for authentication, tenant
  authorization, quotas, durable records, governance, artifact integrity,
  telemetry, backup, and deployment lifecycle.

The complete planned architecture through Stage J now exists as code,
documentation, tests, and explicit decision gates. This does **not** mean Ryuk
is production-certified. The principal remaining work is real GPU/deployment
validation, end-to-end implementation of advanced task types in certified
adapters, representative model-auditor calibration, API-wide control-plane
enforcement, and replacement of single-process reference services with
distributed production infrastructure.

Current automated evidence:

- **163 tests passed**
- **4 optional external integration tests skipped** because their real services
  were not configured
- **Routing evaluation accepted** with no acceptance failures
- **Audit mechanics evaluation accepted** with 100% expected-action agreement
  and zero false accepts on the small four-case mechanics corpus
- Ruff passed
- Mypy passed across 72 source/test/script files
- Python compilation passed
- `git diff --check` passed
- One existing Starlette `TestClient` deprecation warning remains

## 2. Architectural Position

Ryuk's central invariant is preserved:

```text
Ryuk task -> Ryuk deployment/engine boundary -> external inference system
          -> Ryuk result, provenance, attempts, audit, and evaluation
```

External systems do not define Ryuk's internal domain. SGLang native generation,
the Ryuk-native vLLM worker protocol, Dynamo's deployment frontend, and NIM's
managed HTTP protocol remain adapter-local concerns.

The executable routing object is a verified deployment, not merely an engine
name. A deployment combines model identity, exact revision where known, engine,
serving runtime, endpoint identity, capabilities, runtime observations, and
policy signals.

## 3. Completed Work by Stage

### Stage A — Trusted Baseline

Completed outcomes:

- Established Python 3.12 development and validation configuration.
- Added pytest, pytest-asyncio, respx, Ruff, and Mypy tooling.
- Added CI compilation, tests, routing evaluation, audit evaluation, lint, and
  type checking.
- Added typed environment configuration through Pydantic settings.
- Added request-context and request-body-limit middleware.
- Added prompt, token, temperature, timezone, and body-size validation.
- Restricted the mock engine to development and test environments.
- Prevented production startup with the mock enabled.
- Ensured upstream failures return safe public errors without response bodies,
  credentials, or internal details.

### Stage B — Core Domain and Provenance

Completed outcomes:

- Added `ModelRef`, `DeploymentRef`, observed identity, identity assessment, and
  discovery contracts.
- Separated requested model preference from authoritative executed-model
  provenance.
- Added verification states: verified, configured-only, unverified, and
  mismatch.
- Added stable deployment and endpoint identities.
- Added typed text/chat inputs, generation configuration, requirements, trace
  context, outputs, timing, usage, and finish reasons.
- Added adapter result and final inference result boundaries.
- Added ADR-002 for deployment identity/provenance.
- Added ADR-003 for typed task/result envelopes.

### Stage C — Reliable and Auditable Execution

Completed outcomes:

- Added typed failures for unavailable deployments, capacity exhaustion,
  deadlines, cancellation, protocol violations, generation failures, capability
  mismatches, identity mismatches, and invalid engine preferences.
- Added safe retry classifications: same deployment, another deployment, or
  terminal.
- Added end-to-end deadline budgets.
- Added bounded attempt counts and configurable backoff.
- Added generation-time failover, not only availability fallback.
- Added immutable execution-attempt records with IDs, sequence, timestamps,
  duration, deployment, outcome, failure code, and retry classification.
- Propagated cancellation into supported adapter boundaries.
- Replaced blocking SGLang transport with lifecycle-managed `httpx` async I/O.
- Added connection/read/write/pool timeouts, response-size limits, typed status
  mapping, schema validation, identity discovery, and opt-in real integration.
- Added ADR-004 for deadlines, attempts, and failover.

### Stage D — Capability and Runtime Evidence

Completed outcomes:

- Added evidence-bearing capability claims with source, scope, runtime version,
  timestamps, expiry, and confidence.
- Added deterministic hard constraints for task kind, served model, context,
  structured output, streaming, accelerator, topology, data location, and
  production eligibility.
- Unknown or stale evidence fails closed when a capability is required.
- Added typed rejection reasons and safe public rejection reporting.
- Added cached liveness, readiness, admission, capacity, probe timing, expiry,
  and recent execution summaries.
- Added a background runtime collector so request routing does not accumulate
  sequential health-probe latency.
- Added ADR-005 for capability evidence and hard constraints.

### Stage E — vLLM Worker Boundary

Completed outcomes:

- Researched native vLLM `AsyncLLM` integration and controller/worker isolation.
- Selected a dedicated Linux/NVIDIA Ryuk worker rather than importing GPU runtime
  dependencies into the controller.
- Added the Ryuk-native controller-to-worker contract.
- Added health, identity, generation, cancellation, usage, finish-reason, and
  metadata normalization.
- Added an isolated vLLM worker application, Dockerfile, requirements, README,
  preflight, and architecture spike.
- Added bounded responses and safe typed error translation.
- Added unit contract tests and an opt-in real GPU integration test.
- Added ADR-001 for the vLLM worker boundary.

Open gate:

- The real Linux/NVIDIA Kimi contract and benchmark matrix has not run in this
  macOS workspace.

### Stage F — Explainable Routing

Completed outcomes:

- Added deterministic versioned routing policy `ryuk-deterministic-v1`.
- Kept hard capability filtering separate from candidate ranking.
- Added explainable score components for preference, runtime evidence,
  reliability, cost, latency, and curated task suitability.
- Added stable deterministic tie-breaking.
- Recorded policy version, ordered deployment IDs, candidate scores,
  components, explanations, attempt plan, and counterfactuals.
- Added a versioned routing corpus and replay evaluator.
- Added metrics for eligibility, selection, constraint violations, completion,
  deadlines, cost, latency, failover recovery, stability, coverage, and
  uncertainty.
- Added a CI gate and stored routing evaluation report.

Current routing-evaluation result:

- 4 scenarios
- 100% eligibility agreement
- 100% labeled selection agreement
- 0% constraint violations
- 100% completion and deadline success in fixtures
- 100% failover recovery in the labeled failover case
- 100% decision stability
- Quality-label coverage remains 0%; the harness does not fabricate quality or
  accuracy evidence.

### Stage G — Distributed Serving and Managed Products

#### G1: NVIDIA Dynamo

Completed outcomes:

- Added ADR-006 defining the Ryuk/Dynamo responsibility boundary.
- Added a deployment-level Dynamo adapter.
- Ryuk selects a complete Dynamo deployment; Dynamo exclusively selects workers
  and owns KV-aware routing and prefill/decode placement.
- Ryuk does not send worker IDs, prefill IDs, data-parallel ranks, busy
  thresholds, or routing extensions.
- Added pinned Dynamo runtime/topology configuration and provenance.
- Added unit contracts, an opt-in real integration test, and a measured serving
  candidate gate.
- Prevented configuration from marking Dynamo production-eligible while the
  measured ADR-006 gate remains on hold.

Open gate:

- Benchmark direct aggregated, Dynamo aggregated, and—where hardware permits—
  Dynamo disaggregated execution on identical hardware, model revision, images,
  and workloads.

#### G2: NVIDIA NIM

Completed outcomes:

- Added a NIM LLM 2.0.11 standard-mode evaluation pin.
- Added readiness, model, version, metadata, profile, inference, and provenance
  handling behind `NIMEngine`.
- Added fail-closed configured release/profile/model verification.
- Added safe optional bearer authentication within the adapter.
- Added text and chat normalization, typed failures, bounded responses, registry
  configuration, unit contracts, compatibility documentation, and an optional
  licensed integration test.

Open gate:

- Run the licensed NIM contract against an immutable container digest and exact
  supported profile/GPU/model combination.

#### G3: TensorRT-LLM

Completed decision:

- Recorded a deliberate **HOLD**, not a placeholder implementation.
- Verified current documented Kimi-K2.5 support and the relevant Dynamo pin.
- Added a comparable benchmark protocol and machine-readable adoption evaluator.
- Prevented TensorRT-LLM from being enabled while the decision gate is held.

Open gate:

- Demonstrate a workload-specific advantage over the current vLLM baseline on
  identical NVIDIA hardware before approving an adapter.

### Stage H — Advanced Task Contracts

Completed contract and policy outcomes:

- Added explicit ordered streaming events: start, delta, and end.
- Added a cooperative cancellation token.
- Added a bounded object-oriented JSON-schema subset and deterministic output
  validation.
- Added structured-output result semantics.
- Added tool definitions and tool-call output representation without execution.
- Added a first multimodal slice accepting up to eight JPEG, PNG, or WebP HTTPS
  references and rejecting credentialed or local URIs.
- Added separate embedding task/result contracts with batch and vector-shape
  validation.
- Added separate reranking task/result contracts with deterministic score order.
- Added advanced deployment capability profiles and fail-closed rejection for
  unsupported task kind, streaming, cancellation, structured output, tools, or
  media type.
- Added contract tests and semantic documentation.

Important limitation:

- These are Ryuk-owned contracts and validation gates. No current real
  deployment is certified for every advanced feature, and the existing public
  inference adapters do not yet execute all Stage H task families end to end.

### Stage I — Audit and Evaluation Intelligence

Completed outcomes:

- Added deterministic validation for schema, required sections, citation format,
  length, simple language constraints, forbidden policy phrases, and probable
  secret leakage.
- Added structured audit identity for generator and auditor deployments/models.
- Added `AuditReport` with findings, claims, evidence requirements, instruction
  failures, contradictions, uncertainty, and maximum severity.
- Added bounded actions: accept, revise, regenerate, verify, reroute, and
  escalate.
- Added a default maximum of two evaluation iterations.
- Added mandatory independent verification behavior for high-risk tasks.
- Added an explicit untrusted-data threat model covering prompt injection,
  retrieved evidence, citations, tool arguments, generated output, and auditor
  output.
- Added `POST /v1/audit/validate` for deterministic validation and structured
  policy decisions.
- Added ADR-008.
- Added a labeled corpus, evaluator, CI gate, documentation, and stored report.

Important limitation:

- The current four-case corpus validates deterministic policy mechanics only.
  It does not establish factual-audit accuracy or demonstrate that a model
  auditor adds value over deterministic checks.

### Stage J — Production Control-Plane Reference Boundary

Completed reference outcomes:

- Added server-owned principals with tenant IDs and roles.
- Added salted scrypt API-key hashing and constant-time verification.
- Added deny-by-default tenant and function authorization.
- Added per-tenant request, concurrency, and estimated-token admission limits.
- Added `SecretRef` so control-plane configuration can carry secret locators
  without secret values.
- Added classification, allowed-location, retention, and payload-logging
  governance policy.
- Prevented restricted payload logging.
- Added a versioned durable SQLite/WAL execution-record reference store.
- Added tenant-keyed record retrieval to prevent cross-tenant object access.
- Added startup schema-version checking and consistent database backup.
- Added structured telemetry redaction for prompts, outputs, credentials, and
  secrets.
- Added artifact SHA-256, signature-verification, scan-status, and provenance
  gates.
- Added a fail-closed deployment lifecycle: draft, validating, ready, active,
  draining, retired, and failed.
- Added tests for authentication, authorization, quotas, tenant isolation,
  persistence, backup, governance, artifact integrity, telemetry, and lifecycle
  transitions.
- Added ADR-007.

Important limitations:

- The security, quota, governance, and persistence implementations establish
  the reference boundary but are not yet enforced across every public API path.
- Admission state is process-local and unsuitable for multiple controller
  replicas.
- SQLite/WAL is a durable local reference, not a high-availability distributed
  production database.
- External secret resolution, encrypted storage policy, key rotation, enterprise
  identity integration, centralized telemetry, and operational alerting remain
  deployment work.

## 4. Architecture Decision Record Inventory

| ADR | Decision | Current status |
| --- | --- | --- |
| ADR-001 | Native vLLM worker boundary | Implemented; GPU production approval conditional |
| ADR-002 | Deployment identity and model provenance | Implemented |
| ADR-003 | Typed task/result envelope | Implemented incrementally |
| ADR-004 | Deadlines, attempts, and failover | Implemented |
| ADR-005 | Capability evidence and hard constraints | Implemented |
| ADR-006 | Dynamo responsibility boundary | Implemented; measured adoption held |
| ADR-007 | Production control plane | Reference boundary implemented; distributed rollout gated |
| ADR-008 | Audit/evaluation trust boundary | Implemented; model-auditor production use gated |

## 5. Current API and Runtime Surface

Implemented public endpoints:

- `GET /health`
- `GET /inference/engines`
- `POST /inference/generate`
- `POST /v1/inference/chat`
- `POST /v1/audit/validate`

Implemented executable adapters/boundaries:

- deterministic development/test mock;
- async native SGLang generation adapter;
- Ryuk-native vLLM controller adapter and isolated worker;
- Dynamo deployment-level frontend adapter;
- NIM managed deployment adapter.

Not implemented as an executable adapter:

- TensorRT-LLM, by explicit decision gate;
- proprietary providers, which remain optional future fallbacks;
- end-to-end advanced embedding/reranking/multimodal/tool-call execution across
  certified deployments.

## 6. Verification Evidence

Latest complete local validation:

```text
163 passed, 4 skipped, 1 warning
Ruff: passed
Mypy: passed across 72 files
compileall: passed
git diff --check: passed
routing evaluation: accepted
audit mechanics evaluation: accepted
```

Skipped tests and reasons:

1. Dynamo real integration: `DYNAMO_TEST_BASE_URL`, model, and version are not
   configured.
2. NIM real integration: base URL, model, release, and profile are not
   configured.
3. SGLang real integration: `SGLANG_TEST_BASE_URL` is not configured.
4. vLLM real GPU worker: `VLLM_WORKER_TEST_BASE_URL` is not configured.

Known warning:

- FastAPI/Starlette's current `TestClient` path warns that its `httpx` integration
  is deprecated and recommends `httpx2`. This does not fail tests but should be
  resolved before dependency upgrades make it an error.

## 7. Open Items and Risks

### P0 — Required Before Any Production Traffic

#### 7.1 Enforce control-plane security on every API path

Work:

- Authenticate every non-health request.
- Resolve tenant and roles exclusively from trusted server-side identity.
- Authorize every resource and function access.
- Apply admission before inference allocation.
- Release concurrency permits on success, failure, timeout, and cancellation.
- Write tenant-scoped durable execution records for every terminal outcome.
- Add negative API tests for missing, malformed, expired, revoked, cross-tenant,
  and insufficient-role credentials.

Exit criteria:

- Production startup refuses unsecured configuration.
- No client-controlled tenant field is authoritative.
- Cross-tenant and unauthorized operations consistently return safe 401/403
  responses.
- Quota exhaustion returns a typed 429 without contacting inference workers.

#### 7.2 Certify at least two real NVIDIA deployments

Work:

- Pin model artifact/revision, container digest, engine/runtime version, GPU
  topology, driver, CUDA, quantization, tokenizer/template, and parallel config.
- Run identity, generation, cancellation, timeout, overload, malformed-response,
  failover, and recovery tests.
- Record TTFT, inter-token latency, end-to-end latency, throughput, error rate,
  utilization, memory, and estimated cost.
- Verify that output provenance matches the deployment that actually executed.

Exit criteria:

- Two deployments pass the same versioned contract and benchmark corpus.
- Failover between them succeeds under a real generation failure.
- Neither deployment relies on configured-only model identity in production.

#### 7.3 Replace reference coordination/storage for multi-replica production

Work:

- Select a transactional durable database and migration system.
- Implement the execution-record store boundary with tenant isolation and
  append/idempotency semantics.
- Select distributed quota/admission coordination.
- Add concurrency, failover, network partition, and retry tests.
- Define retention deletion, legal hold, export, backup, and restore operations.

Exit criteria:

- Multiple controllers enforce one consistent quota.
- Duplicate request delivery does not create conflicting executions.
- Database failover and restore meet documented RPO/RTO.
- Tenant isolation survives concurrent and adversarial tests.

#### 7.4 Supply-chain and secret-management enforcement

Work:

- Resolve `SecretRef` through the selected secret manager.
- Add automated credential rotation and revocation.
- Require immutable image digests.
- Generate and retain SBOM/provenance.
- Scan dependencies, containers, operating-system packages, and model-serving
  images.
- Verify signatures/attestations before deployment activation.

Exit criteria:

- No production secret value is present in repository configuration, logs,
  telemetry, provenance, or execution records.
- A failed signature or scan prevents activation.
- Rotation succeeds without uncontrolled downtime.

### P1 — Required for the Intended Product Capabilities

#### 7.5 Implement Stage H end to end

Work one vertical slice at a time:

1. Streaming and cancellation through API, router, adapter, and client disconnect.
2. Structured output generation plus deterministic post-validation and typed
   invalid-output handling.
3. Tool-call output through API and adapters, still without tool execution.
4. Multimodal execution through one exact validated model/deployment and a safe,
   allowlisted media-fetch boundary.
5. Embedding execution through a dedicated adapter/task/result path.
6. Reranking execution through a dedicated adapter/task/result path.

Exit criteria for each slice:

- Semantic contract, capability evidence, API, adapter, typed failures, fixtures,
  and evaluation criteria all pass.
- Unsupported deployments are rejected rather than emulated.
- Cancellation releases worker and quota capacity.

#### 7.6 Calibrate model-based audit

Work:

- Build a representative labeled corpus covering factual claims, unsupported
  claims, citations, contradictions, instruction adherence, uncertainty, prompt
  injection, and secret exfiltration.
- Separate generator and auditor identities and test same-model bias.
- Measure false accepts, false rejects, severity calibration, action accuracy,
  latency, and cost.
- Compare deterministic-only, model-only, and combined policies.
- Add independent verification sources for high-risk cases.

Exit criteria:

- Model audit demonstrates measured incremental value over deterministic rules.
- False-accept tolerance is defined by risk tier.
- The bounded policy cannot loop indefinitely or execute auditor-suggested tools.

#### 7.7 Dynamo and TensorRT-LLM decisions

Work:

- Complete the ADR-006 direct/Dynamo aggregated/Dynamo disaggregated comparison.
- Use the serving-candidate evaluator with comparable records.
- Run the TensorRT-LLM Kimi candidate spike only on a supported pinned platform.

Exit criteria:

- Adopt Dynamo only for workloads with measured benefit after operational cost.
- Implement TensorRT-LLM only if it beats an existing candidate on a defined
  workload without unacceptable reliability or complexity regression.

### P2 — Operational Hardening

#### 7.8 Observability and incident response

- Export metrics, traces, logs, routing decisions, attempts, audits, and control
  events to the selected observability stack.
- Define SLIs/SLOs for availability, deadline success, accepted-result latency,
  errors, capacity, audit outcomes, and failover.
- Add alerting, runbooks, dashboards, correlation IDs, and safe sampling.
- Ensure prompt/output logging is disabled or governance-approved.

#### 7.9 Load, soak, and chaos testing

- Load: validate quotas, queueing, deadlines, throughput, and overload behavior.
- Soak: detect connection, memory, task, database, and telemetry leaks.
- Chaos: terminate workers, interrupt networks, stale discovery, exhaust capacity,
  fail the record store, and simulate partial dependency recovery.
- Verify chaos cannot cause cross-tenant access or mock fallback in production.

#### 7.10 Backup and disaster recovery

- Automate encrypted backups with retention.
- Perform scheduled restore drills into isolated infrastructure.
- Reconcile execution records and deployment state after restore.
- Record demonstrated RPO/RTO rather than configuration targets alone.

#### 7.11 Dependency and warning cleanup

- Resolve the Starlette `TestClient`/`httpx` deprecation warning.
- Establish automated dependency update and compatibility policy.
- Add license and vulnerability review gates.

## 8. Recommended Execution Sequence

The next implementation program should proceed in this order:

1. **API-wide authentication, tenant authorization, and admission enforcement.**
   This closes the largest gap between reference primitives and actual behavior.
2. **Durable execution-record integration.** Persist requests, routing decisions,
   attempts, provenance, audit reports, evaluation decisions, and terminal state.
3. **Production configuration gate.** Refuse startup unless authentication,
   durable storage, secret resolution, mock prohibition, and required deployment
   identity are configured.
4. **Real two-deployment NVIDIA certification.** Prefer the existing vLLM worker
   and one SGLang or NIM deployment before adding another engine.
5. **Streaming/cancellation vertical slice.** It exercises API lifecycle,
   disconnect handling, adapter cancellation, quota release, and execution
   records together.
6. **Structured-output vertical slice.** Reuse deterministic schema validation
   and audit/evaluation actions.
7. **Representative audit calibration.** Do not deploy model-based audit based on
   the current mechanics fixture.
8. **Distributed storage and admission.** Required before controller replicas or
   production HA.
9. **Load/soak/chaos and disaster-recovery certification.** Required before a
   production launch decision.
10. **Revisit Dynamo and TensorRT-LLM only with comparable benchmark evidence.**

## 9. Proposed Production-Readiness Definition

Ryuk may be called production-ready for its first slice only when all of the
following are true:

- Every public operation is authenticated, tenant-authorized, quota-controlled,
  and auditable.
- At least two verified real deployments pass contract and failure tests.
- Hard constraints, deadlines, cancellation, attempts, and failover work under
  real load.
- Every result records exact deployment/model/runtime provenance.
- No mock can execute in production.
- Durable records survive controller restart and database failover.
- Secrets, restricted payloads, and upstream error bodies are absent from logs
  and records.
- Artifact integrity and scan gates prevent unsafe activation.
- Routing and audit policy changes pass versioned evaluation gates.
- Backup restore, load, soak, chaos, key rotation, and incident-response drills
  meet documented acceptance criteria.

## 10. Repository and Change-Management Status

The current workspace contains a large set of modified and untracked files from
the complete migration. This is an important operational risk even though all
local validation passes.

Required cleanup before handoff:

- Review the complete diff by logical stage.
- Confirm that `AGENTS.md`, architecture documents, ADRs, fixtures, reports,
  workers, scripts, and CI files should all be version-controlled.
- Keep `llms.md` untouched unless the owner explicitly requests otherwise; it is
  currently untracked and treated as user-owned.
- Create small, reviewable commits grouped by architecture/domain, execution,
  adapters, routing/evaluation, advanced contracts/audit, and control plane.
- Tag the first coherent baseline only after CI passes from a clean checkout.

No destructive cleanup, reset, or commit was performed as part of this report.

## 11. Bottom Line

Ryuk's planned A–J architecture is implemented and locally verified as a strong
control-plane foundation. The project has crossed from proof-of-concept structure
into a testable platform architecture.

The remaining gap is not another broad redesign. It is production realization:
enforce the control plane on actual APIs, certify real GPU deployments, implement
advanced features vertically, calibrate audit on representative evidence, move
state and quotas to distributed services, and prove the system under operational
failure.
