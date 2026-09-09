# Ryuk Whole-Project and Development-Phase Review

**Review date:** 2026-09-09
**Repository:** `/home/sudosu/projects/ryuk`
**HEAD inspected:** `907f7e8` — `Harden distributed control plane foundation`
**Parent implementation commit:** `1fb0ff6` — `Document next-session Phase 2 handoff`
**Companion documents:** `RYUK_ARCHITECTURE_DESIGN.md`, `RYUK_DEVELOPMENT_PHASE_PLAN.md`
**Review type:** Consolidated engineering and architecture review

## Executive assessment

Ryuk now has a credible **inference control-plane foundation**. The historical `ARCHITECTURE_REVIEW.md` correctly identified the original risks, and the later implementation work addresses many of them: deployment identity, typed results, capability evidence, deadlines, generation-time failover, explainable routing, adapter isolation, audit mechanics, and a reference API control plane.

Ryuk is **not yet the orchestration system described in the target design**. The current code does not yet contain a durable workflow/task graph, conversation store, context builder, automatic model-specific token fitting, persistent memory, retrieval pipeline, tool executor/sandbox, Kimi K3 profile, DeepSeek V4 profile, or an end-to-end multi-model coding workflow. The advanced contracts represent these capabilities; they do not execute them through certified deployments.

The correct current product statement is:

> Ryuk can govern and route typed inference requests through replaceable deployment adapters. It cannot yet safely claim durable multi-step delegation or production model performance.

## Scope and evidence quality

I inspected:

- All repository paths under `backend/`, `workers/`, `tests/`, `scripts/`, `docs/`, configuration and requirements files.
- `AGENTS.md`, `ARCHITECTURE_REVIEW.md`, `IMPLEMENTATION_PLAN.md`, `PROJECT_STATUS_REPORT.md`, README, all ADRs, integration notes, evaluation reports, the next-session handoff, and the two proposed design/phase documents.
- Current Git history, the `907f7e8` change set, route wiring, registry/router, deployment adapters, runtime collector, control-plane modules, contracts and tests.

The older status report records **180 passed, 4 skipped, 1 warning** at its
September 1 checkpoint. The current `907f7e8` change set was independently
verified in the supported `ryuk-ai` environment as follows:

- Full suite with live local PostgreSQL and Redis: **199 passed, 5 skipped, 1 warning**.
- PostgreSQL durability/reopen and tenant-isolation contracts: passed.
- Redis shared admission, atomic contention and active-permit lifetime contracts: passed.
- Python compilation: passed.
- Ruff over `backend tests scripts`: passed.
- Mypy over `backend tests scripts`: passed.
- Routing evaluator: accepted; four fixture scenarios, 100% eligibility/selection agreement, 0% constraint violations, 100% failover recovery, 0% quality-label coverage.
- Audit evaluator: accepted; four mechanics cases, 100% action agreement, 0% false accepts on that small corpus.
- `git diff --check`: passed.

The five remaining skips require real Dynamo, self-hosted NIM, hosted NVIDIA
NIM, SGLang and vLLM services. The warning is the known Starlette
`TestClient`/httpx migration warning. Local PostgreSQL and Redis were stopped
after verification.

## Repository state and change-management finding

The reviewed implementation is committed at `907f7e8`; `main` is one commit
ahead of `origin/main`. This consolidated review document is the only new file
after that commit and is intended to record the updated architectural truth.

The commit includes quota-policy visibility, production readiness checks,
same-tenant request constraints, PostgreSQL records, Redis admission, Vault KV
resolution, stronger activation/artifact gates, hosted NVIDIA NIM groundwork,
real-service integration runners, and corresponding tests.

The architecture and phase-plan documents are tracked at the repository root. Their `Proposed` status is appropriate; they do not imply that orchestration or memory exists.

For current planning, use this review together with
`RYUK_ARCHITECTURE_DESIGN.md`, `RYUK_DEVELOPMENT_PHASE_PLAN.md`, and the latest
next-session handoff. `ARCHITECTURE_REVIEW.md` and `PROJECT_STATUS_REPORT.md`
remain valuable historical records, but their repository snapshots and test
counts are superseded by this review.

## What is strong and should be preserved

1. Ryuk owns internal inference/result contracts rather than exposing vendor SDK objects.
2. Model identity is separate from caller preference and deployment identity is represented explicitly.
3. A deployment is more than an engine name: model, engine, runtime, endpoint and capability evidence are separated.
4. Capability hard constraints are evaluated before policy ranking; unknown required evidence fails closed.
5. Attempts, deadlines, typed retry classifications and generation-time failover are represented.
6. SGLang transport is asynchronous and bounded; vLLM is isolated behind a GPU worker.
7. Dynamo is treated as a deployment/serving topology rather than as a worker-level peer router.
8. NIM and managed serving protocols remain adapter-local.
9. Routing policy is deterministic, versioned and explainable instead of pretending the fixture has quality evidence.
10. Audit and evaluation remain separate, bounded and untrusted with respect to tool authority.
11. Mock inference is development/test-only and production startup rejects it.
12. API authentication, role checks, quotas, records, governance, artifact checks and lifecycle primitives are now real code rather than only recommendations.
13. The design explicitly separates persistent state, application caches and serving KV cache.

## Phase status against the proposed development plan

| Phase | Status | Assessment |
| --- | --- | --- |
| 0. Rebaseline | Complete and documented | Baseline report, matrices, traceability and evidence inventory exist; full suite was not freshly reproduced here |
| 1. Govern every API | Complete for the current route surface | Current non-health routes have server-owned API-key authentication, roles, admission, records and redacted events; production operational certification remains open |
| 2. Certify two deployments | Offline adapter groundwork only | Hosted NIM contracts and an opt-in two-model integration test exist, but the real external test remains skipped and no exact deployment is certified |
| 3. Durable single-task workflow | Not implemented | No workflow/task graph, leases, checkpoints, recovery coordinator or tool ledger exists |
| 4. Conversations/context | Not implemented | Current API accepts caller messages and optional required context tokens; no durable conversation/context builder/fit/compaction exists |
| 5. Tool/sandbox boundary | Contracts only | Tool-call representation exists, but there is no authorized tool gateway or isolated repository executor |
| 6. Kimi–DeepSeek coding workflow | Not implemented | No model-specific profiles, coding task decomposition, patch workspace, tests-as-artifacts or bounded handoff exists |
| 7. Persistent memory | Not implemented | No memory scopes, memory evidence, source store, embedding index, reranker path or deletion propagation exists |
| 8. Specialist modalities | Contracts/adapter groundwork only | No end-to-end ASR, OCR/layout, embedding, rerank, image/video workflow is certified |
| 9. Caching/routing optimization | Routing foundation exists; semantic cache absent | Runtime state and deterministic routing exist; application result cache and evidence promotion do not |
| 10. Distributed production | Implementation foundation; not certified | PostgreSQL records and Redis admission are real and locally integration-tested; leases/reconciliation, partitions, restore, RPO/RTO and multi-replica chaos evidence remain open |
| 11. Production certification | Not started | No real model integration, benchmark, load/soak/chaos, restore or operational certification |

### Important sequencing correction

The handoff says not to begin Phase 3 until the Phase 2 real-deployment evidence exists. That is a safe production-activation gate, but it is unnecessarily serial for development. Split Phase 2 into:

- **2A: offline profile and contract preparation** — typed Kimi/DeepSeek deployment profiles, sanitized fixtures, endpoint semantics and adapter tests without protected data.
- **2B: external certification** — authorized credentials, real identity/limits/failure/cancellation tests and benchmark evidence.

Permit workflow-schema development and local crash/recovery tests after 2A, using mock and contract fixtures, while 2B runs in parallel. Do not allow real production activation, performance claims or protected data until 2B passes. This avoids making provider access the critical path for controller correctness while preserving the safety gate.

## Prioritized findings

### P0 — No real deployment evidence

All real Dynamo, NIM, SGLang and vLLM integration tests are skipped without configured services. The repository contains simulated contracts and an opt-in vLLM worker, but no real Kimi K3 or DeepSeek V4 identity, limit, cancellation, failure, latency, throughput or cost evidence.

**Impact:** Routing and provenance are structurally testable, but production capability and model-quality claims are not established.

**Action:** Complete Phase 2A/2B with two exact immutable profiles. Record model/revision, adapter/runtime, endpoint contract, limits, identity evidence, settings, hardware where known, and benchmark conditions. Do not put credentials or protected payloads in fixtures.

### P0 — No durable orchestration implementation

There is no workflow coordinator, task dependency model, conversation identity, checkpoint/restart protocol, lease/fencing model, idempotent task creation, or task-level acceptance state. `ExecutionRecord` is a terminal/API record reference, not a resumable workflow engine.

**Impact:** Ryuk cannot yet safely resume `X+Y` or `X+Y+Z`, distinguish accepted artifacts from successful calls, or recover multi-model work after controller failure.

**Action:** Implement Phase 3 after Phase 2A: single-task durable state, then add dependency edges, task packets, leases, recovery and bounded scheduler. Keep the external deployment gate separate.

### P0 — Context handling is still caller-declared, not engineered

`required_context_tokens` is an optional requirement checked against a capability claim. The public API does not automatically count formatted messages, reserve output/reasoning tokens, assemble scoped evidence, compact history or re-tokenize on fallback. Tokenization exists in the vLLM worker, not in a Ryuk context pipeline.

**Impact:** A request can pass the current capability check while the actual formatted prompt plus output reserve does not fit the selected model. Model switching can invalidate assumptions.

**Action:** Phase 4 must introduce a context builder and deployment-specific preparation result containing payload digest, tokenizer/template revision, exact/estimated count method, input count, output reserve, safety margin and media accounting. Reprepare every fallback candidate.

### P1 — Kimi/DeepSeek product intent is not represented in runtime configuration

The current registry tests and compatibility notes use Kimi K2-era identifiers such as `moonshotai/Kimi-K2` and `Kimi-K2.5`. `Settings` has generic `kimi_api_url`/credential fields, but no registered Kimi K3 or DeepSeek V4 deployment profile. The routing policy has generic suitability fields, not measured task-specific profiles.

**Action:** Add distinct model/artifact/deployment configuration and contract fixtures only after current official endpoint contracts are rechecked. Keep “preferred model” separate from “verified executed model.” Test DeepSeek tool support rather than assuming it.

### P1 — Advanced task support is representation-level

`advanced.py` correctly defines streaming events, cancellation, structured output, tool-call representation, multimodal inputs, embeddings and reranking. The tests explicitly verify that tool calls are representation-only. No tool executes, no stream endpoint exists, and no real embedding/rerank/ASR/OCR/video adapter is wired to a workflow.

**Action:** Implement one vertical slice at a time, starting with streaming/cancellation or retrieval, with API, adapter, capability, failure, security and acceptance tests together.

### P1 — Distributed control plane is implemented but not HA-certified

The current SQLite/WAL and process-local implementations remain useful local
components. PostgreSQL records and Redis admission now provide concrete
multi-process boundaries and pass local real-service contracts. They do not yet
provide workflow leases/fencing or prove behavior under database/Redis failover,
network partitions, controller death, or multi-region deployment.

**Action:** Keep the new implementations behind their Ryuk-owned interfaces.
Before production replicas, add permit lease/crash reconciliation, migration
policy, outbox/inbox semantics where required, backup/restore, RPO/RTO and
adversarial partition/chaos tests.

### P1 — Vault resolution exists without operational certification

`resolve_secret_ref` now supports environment references plus an explicitly
configured TLS Vault KV manager. Production NIM configuration requires a
`vault:` locator and HTTPS Vault address. This is a sound adapter boundary, but
workload authentication, renewal, rotation, revocation and outage behavior are
not yet operationally certified.

**Action:** Add a provider abstraction and operational rotation/revocation tests before production, without storing resolved values in configuration, logs, records or provenance.

### P1 — Terminal recording is not yet failure-isolated from request delivery

Current route handlers record terminal state in `finally`. If the record store raises during `record_terminal`, it can mask an otherwise completed inference response or replace the original failure. That may be acceptable as fail-closed control behavior only if explicitly specified; currently the semantics are not documented or tested for store failure.

**Action:** Decide and test the contract: either terminal-record persistence is part of successful completion and the request fails safely when it cannot commit, or use an outbox/append worker with an explicit “response delivered, record pending” state. Never silently lose the record.

### P1 — Redaction is shallow

`ControlEvent.safe_attributes()` removes a small set of exact top-level keys. Nested dictionaries, lists, alternate key spellings and future adapter metadata can still carry sensitive data.

**Action:** Use typed event schemas or recursive structural redaction with allowlisted fields. Add nested secret, authorization, prompt and output tests. Treat raw adapter metadata as untrusted until sanitized.

### P1 — Current production readiness checks are necessary but incomplete

The startup gate verifies active keys, quota tenants, durable reference-store health and eligible verified deployment identity. It does not establish distributed coordination, secret-manager availability/rotation, artifact signature/scan evidence for every actual deployment, encryption, alerting, restore evidence or real model contract performance.

**Action:** Keep startup checks narrow and fail closed; do not label the process production-certified until the operational gates are demonstrated externally.

### P2 — Test environment and dependency warning need cleanup

The documented suite has an existing Starlette `TestClient`/httpx migration warning. The current restricted runner also cannot create the stream descriptor needed by middleware/TestClient tests and cannot write repository caches.

**Action:** Resolve the pinned `httpx2` migration warning in the supported environment, document the supported test invocation, and ensure CI uses a writable checkout. Do not “fix” the warning by weakening tests or making the app depend on sandbox quirks.

### P2 — Empty adapter modules are deliberate but easy to misread

`backend/inference/engines/vllm.py` and `tensorrt_llm.py` are empty while `vllm_worker.py` and managed adapters provide the current paths. This is consistent with the ADRs if clearly documented, but a future contributor may interpret empty modules as unfinished universal adapters.

**Action:** Add short module-level documentation or remove unused placeholders only in a deliberate cleanup change. Keep TensorRT-LLM on HOLD until its benchmark gate passes.

## Review of the architecture design

The proposed architecture is directionally correct and aligns with the historical review:

- It routes composed deployments, not flat engines.
- It makes the controller/worker and Dynamo boundaries explicit.
- It treats planning as bounded work under ordinary authorization.
- It separates source content, working state, selected memory, application cache and serving KV cache.
- It makes model results and reviews untrusted until deterministic/evaluation policy accepts them.
- It retains provenance through model handoffs.

The next design refinement should be a concrete **workflow state-machine ADR** and a **context preparation ADR**. The ER diagram is conceptual; it is not yet a migration schema. Before implementation, specify transaction boundaries, tenant-qualified keys, state-transition invariants, idempotency, artifact revision binding and deletion/retention behavior.

## Review of the development phase plan

The plan's order is sound for production safety:

1. Establish truth and API authority.
2. Prove deployment identity and failure behavior.
3. Make work durable.
4. Engineer context.
5. Isolate tools.
6. Add Kimi/DeepSeek workflows.
7. Add persistent memory.
8. Add specialists.
9. Optimize caches/routing.
10. Scale and certify.

The following changes improve execution:

- Split Phase 2 into offline profile preparation and real deployment certification so workflow development is not blocked by access to provider infrastructure.
- Add explicit owners, decision dates and evidence locations to each phase; the current plan names product-owner decisions but not responsible implementers.
- Add a migration/rollback gate to every state or persistence phase.
- Add a “no protected data” gate before external endpoint certification is configured.
- Treat terminal-record failure semantics as a Phase 1 decision, not a later database detail.
- Make the first workflow task graph deterministic; defer model-generated decomposition until single-task recovery and tool authority are proven.
- Make benchmark corpora and accepted thresholds first-class artifacts, not narrative notes.
- Keep Phase 7 memory behind a source/evidence/deletion ADR; vector search is not a substitute for durable truth.

## Recommended next 10 engineering actions

1. Push or otherwise publish reviewed commit `907f7e8` through the normal repository workflow.
2. Remove the TestClient/httpx warning using the project's pinned dependency policy.
3. Decide hosted-first versus self-hosted-first, data classification/residency, authorized credentials and identity evidence policy.
4. Complete Phase 2A immutable profiles for Kimi K3 and DeepSeek V4 (or approved substitutes) with no credentials or protected payloads.
5. Expand sanitized contract fixtures for message ordering, reasoning settings, output limits, streaming, tools, errors and identity discovery.
6. Run Phase 2B only after the product-owner decisions and access controls are explicit; record external skips honestly.
7. Draft the workflow-state ADR and implement a local single-task state machine while external certification runs.
8. Decide and test terminal-record failure semantics and duplicate terminal records.
9. Replace shallow event redaction with typed allowlisted schemas or recursive structural redaction and adversarial tests.
10. Complete Redis crash reconciliation and PostgreSQL restore evidence before treating the distributed foundation as production-ready.

## Final verdict

The project has a strong, disciplined inference foundation and the architecture is substantially improved over the original proof of concept. The phase plan is appropriate, with the Phase 2/Phase 3 dependency split recommended above.

The largest risk is not another model adapter. It is claiming “orchestration” before Ryuk owns durable workflow state, model-specific context preparation, authorized tool execution and persistent evidence. The next milestone should therefore be the verified deployment-profile boundary plus a restart-safe single-task workflow—not an unrestricted multi-agent loop or a large memory framework.
