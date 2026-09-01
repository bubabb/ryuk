# Ryuk Step-by-Step Development Phase Plan

**Date:** 2026-09-01
**Status:** Proposed execution plan
**Companion design:** `RYUK_ARCHITECTURE_DESIGN.md`
**Repository reviewed:** `/home/sudosu/projects/ryuk`, HEAD `04a113884bedacaeb7d4d0a19538c387736fc6b4`

## 1. Goal and planning position

This plan turns the target architecture into small, gated development phases. It extends—not replaces—the repository's existing A–J implementation plan and ADRs.

The existing project already contains a substantial inference-control foundation: typed tasks/results, deployment identity and capabilities, deadlines and attempts, routing policy, runtime state, multiple adapter boundaries, audit/evaluation mechanics, and reference security/control-plane components. The next program should integrate and prove these pieces before introducing a broad autonomous-agent framework.

The implementation order is:

```mermaid
flowchart LR
    P0["0. Rebaseline"] --> P1["1. Govern every API"]
    P1 --> P2["2. Certify two deployments"]
    P2 --> P3["3. Durable single-task workflow"]
    P3 --> P4["4. Context and conversations"]
    P4 --> P5["5. Safe coding tools"]
    P5 --> P6["6. Kimi–DeepSeek workflow"]
    P6 --> P7["7. Persistent memory"]
    P7 --> P8["8. Specialist modalities"]
    P8 --> P9["9. Caching and routing optimization"]
    P9 --> P10["10. Distributed production"]
    P10 --> P11["11. Production certification"]
```

Do not advance because code exists. Advance only when the phase's exit evidence is recorded.

## 2. Delivery rules applying to every phase

1. Inspect the current code and Git state before editing; preserve unrelated user changes and keep `llms.md` owner-controlled.
2. Write or approve the relevant ADR before introducing a durable architectural boundary.
3. Use Ryuk-owned typed contracts. Contain external protocol and SDK types inside adapters.
4. Implement the smallest vertical slice that can be tested end to end.
5. Add unit, contract, integration, security, and recovery tests in proportion to the change.
6. Record exact external model, endpoint, runtime and infrastructure versions used for evidence.
7. Run formatting, linting, static typing, compilation and applicable tests before merge.
8. Inspect the full diff and `git diff --check`; scan for credentials and generated files.
9. Update the implementation/status documents with observed evidence and known limitations.
10. Use feature flags and reversible migrations when rollout risk is material.

Each change set should be independently reviewable. Do not combine state-machine changes, a new hosted adapter, persistent memory, and distributed deployment into one pull request.

### Evidence labels

Use these terms consistently:

- **Implemented:** Code and local automated tests exist.
- **Integration-tested:** The exact external boundary was exercised.
- **Benchmark-evaluated:** A versioned workload produced comparable measurements.
- **Production-certified:** Security, operational, failure and recovery gates passed on the intended deployment.
- **Unknown:** No current evidence. Unknown must never be presented as false, zero, free or supported.

## 3. Program success criteria

The first orchestration release is successful when Ryuk can accept an authenticated coding task, resume it after controller restart, select an eligible Kimi or DeepSeek deployment, construct model-specific bounded context, obtain a patch, execute authorized tests in an isolated workspace, perform bounded repair or review when policy requires, and return an accepted result with complete provenance.

The complete program additionally requires scoped persistent memory, specialist ingestion, deletion/correction propagation, distributed coordination where needed, and production recovery evidence.

## Phase 0 — Rebaseline and freeze architectural truth

### Objective

Establish a clean, reproducible baseline and resolve contradictions between the historical architecture review and the current repository.

### Steps

1. Capture branch, commit, working-tree status, Python/tool versions and supported host environment.
2. Run the repository's documented compilation, lint, type and test commands from a clean dependency environment.
3. Reproduce the four externally skipped tests and document why each is skipped.
4. Inventory all public API routes and map them to authentication, authorization, admission and record-writing behavior.
5. Inventory deployment adapters and mark every task capability as configured, integration-tested, benchmarked or unknown.
6. Create a traceability table from ADR-001–008 and both architecture documents to current modules/tests.
7. Decide which generated design document becomes project documentation and review it before copying into the repository.
8. Open issues for every confirmed gap; do not treat historical findings already fixed as new work.

### Deliverables

- Baseline verification report with raw command results.
- API enforcement matrix.
- Deployment/capability evidence inventory.
- ADR and requirement traceability matrix.
- Prioritized issue list with owners or explicit unassigned status.

### Verification

- Full existing suite passes or failures are understood and recorded.
- A clean checkout can reproduce the same result.
- No credentials or user-owned files enter commits.
- Historical claims such as “no tests exist” are explicitly marked obsolete.

### Exit gate

Do not begin feature work until the baseline is green or an approved exception identifies the exact failure, risk and containment.

## Phase 1 — Enforce the control plane on every public operation

### Objective

Close the largest immediate production gap: security/control primitives must govern actual API execution, including direct inference and audit endpoints.

### Steps

1. Define route classes: health, inference, workflow, audit/evaluation, deployment administration and memory administration.
2. Establish a server-owned `Principal` for every non-health request. Never accept authoritative tenant or role fields from callers.
3. Apply tenant-and-role authorization before registry, record, artifact or memory access.
4. Run admission before model allocation. Reserve request, concurrency and estimated-token budgets.
5. Guarantee permit release on success, typed failure, timeout, cancellation and disconnected streaming clients.
6. Integrate durable terminal execution records for direct inference and audit; exclude secrets and restricted payloads.
7. Resolve `SecretRef` only inside the authorized adapter/deployment boundary.
8. Add a production startup gate requiring authentication, safe secret resolution, durable storage, mock prohibition and required identity policy.
9. Add safe error mappings for authentication, authorization and quota failure without leaking upstream or resource existence.
10. Instrument redacted request, admission and terminal-outcome events.

### Suggested code areas

- Extend `backend/control/security.py`, `admission.py`, `records.py`, `governance.py` and configuration.
- Add thin FastAPI dependencies/middleware rather than duplicating checks in every handler.
- Preserve current inference contracts and router behavior beneath the new boundary.

### Required tests

- Missing, malformed, expired and revoked credentials.
- Insufficient role and cross-tenant object access.
- Quota rejection proves no inference adapter was contacted.
- Concurrent permit accounting and release for every terminal path.
- Production startup rejects mock/unsecured/secret-invalid configurations.
- Logs and records contain no credential, raw authorization header or prohibited payload.

### Exit gate

Every public operation is either explicitly public or authenticated, authorized, admitted and recorded. Negative tests demonstrate fail-closed behavior.

## Phase 2 — Certify two real model deployments

### Objective

Provide truthful Kimi K3 and DeepSeek V4 deployment profiles—or formally approved substitutes—before building routing decisions on catalog descriptions.

### Decision checkpoint

Choose hosted-first or self-hosted-first based on authorized credentials, data classification, available hardware, budget and residency. This phase does not authorize purchasing compute or changing external accounts.

### Steps

1. Create separate immutable deployment profiles for each exact endpoint/runtime. Do not create one generic “NVIDIA chat” profile.
2. Record model name/artifact identity, revision evidence, adapter version, external endpoint contract date, supported roles/modalities, context/input/output limits, reasoning settings, sampling constraints, streaming and cancellation behavior.
3. For self-hosted profiles, also pin image digest, engine/runtime, tokenizer/template, quantization, driver/CUDA, GPU topology and parallel configuration.
4. For hosted profiles, explicitly mark artifact digest, hardware or runtime details unavailable to Ryuk; define what identity evidence policy accepts.
5. Implement or harden adapter-local translations. The external OpenAI-compatible interface may stay at that adapter boundary; Ryuk contracts remain authoritative.
6. Exercise authentication, ordinary generation, maximum safe payload behavior, structured output or patch schema, streaming, timeout, overload, malformed response, async `202` behavior if exposed, cancellation and usage accounting.
7. Test Kimi tool calls. Test rather than assume DeepSeek tool support; use patch-only structured output if its selected profile lacks a verified tool contract.
8. Run real generation failure and cross-deployment failover without losing provenance.
9. Store only sanitized fixtures. Never save the account key or provider response headers containing sensitive identifiers.
10. Add activation policy: unknown/stale hard constraints reject the deployment for that task.

### Benchmark corpus

Include small fixes, multi-file changes, bug localization, test repair, code explanation and at least one screenshot-driven task for Kimi. Use pinned repositories/revisions and deterministic acceptance tests. Run equivalent reasoning/sampling profiles where possible and record unavoidable differences.

### Measures

- Accepted-patch and test-pass rates.
- End-to-end latency, time to first token, output rate and failure rate where available.
- Input/output/reasoning usage and estimated cost.
- Schema/tool validity, cancellation effectiveness and retry behavior.
- Identity/provenance completeness.

### Exit gate

Two real profiles pass the same versioned core contract. Their differences are represented explicitly, failover works under real failure, and no result is attributed from the caller's requested model alone.

## Phase 3 — Build a durable single-task workflow

### Objective

Add resumable workflow state above the existing inference router without yet adding autonomous multi-model planning.

### ADR first

Approve an ADR covering state transitions, transaction boundaries, leases/fencing, event ordering, idempotency, cancellation, and uncertain external effects.

### Steps

1. Define `Workflow`, `Task`, `TaskDependency`, `TaskEvent`, `TaskPacket`, `ArtifactRef` and workflow-level budget contracts by extending—not duplicating—existing inference concepts.
2. Implement explicit states such as pending, ready, leased/running, waiting, succeeded, failed, cancelled and blocked.
3. Distinguish inference success from task acceptance.
4. Add optimistic transition versions and immutable ordered events.
5. Implement a local transactional scheduler that claims ready tasks with leases and fencing tokens.
6. Allocate one workflow deadline/cost/task budget downward so retry layers cannot multiply work independently.
7. Dispatch one inference task through the existing router and attach all resulting attempts/provenance to the workflow task.
8. Persist task output as a versioned artifact, then perform deterministic validation before committing acceptance.
9. Add idempotent workflow creation and request replay behavior.
10. On startup, reconcile expired leases and uncertain calls; schedule only eligible unfinished work.
11. Implement cancellation propagation to queued/running inference and record late results without accepting them.
12. Expose create/status/cancel/result APIs with tenant-scoped authorization.

### Storage approach

Use a single transactional database for the initial controller. An external queue is unnecessary until measured scale demands it. If a queue is introduced, publish through an outbox or equivalent so database commit and dispatch cannot silently diverge.

### Required tests

- State-transition property tests and invalid transition rejection.
- Duplicate request delivery and duplicate worker completion.
- Crash immediately before and after dispatch/commit.
- Lease expiry with a stale worker attempting to commit.
- Deadline exhaustion, cancellation and late upstream output.
- Tenant isolation across workflow, task and artifact identifiers.
- No workflow path silently falls back to mock in production.

### Exit gate

A single model task survives controller restart without duplicate accepted work, lost provenance or inconsistent status.

## Phase 4 — Add conversations and deployment-specific context preparation

### Objective

Make conversation continuity and context-window handling Ryuk-owned, reproducible and safe across model switches.

### ADR first

Define context sources, trust tiers, preparation/counting provenance, fallback fitting, compaction, snapshot retention and deletion behavior.

### Steps

1. Add durable `Conversation`, `Message` and content-reference records scoped to tenant/project/user policy.
2. Keep authoritative source content separate from workflow working state and summaries.
3. Implement a `ContextBuilder` that selects trusted instructions, objective, acceptance criteria, relevant recent turns, task state, source excerpts and accepted artifacts.
4. Add a deployment-specific preparation request/result at the adapter or worker boundary.
5. Apply the target chat template and tokenizer where available; return tokenizer/template/profile revision, exact or estimated count method and prepared-payload digest.
6. Enforce input plus reserved output plus safety margin against the candidate profile. Enforce separate media and output constraints.
7. Ensure execution uses the counted payload/configuration or requires re-preparation.
8. On fallback, re-prepare and revalidate rather than reusing token counts or serialized chat.
9. Implement deterministic context exclusion/deduplication before model summarization.
10. Add source-linked checkpoint compaction with constraints, decisions, open questions and source references.
11. Test whether critical facts remain accessible across early/middle/late placement and compaction for actual candidate models.
12. Expose transparent metadata: selected source references, truncation/compaction event and count confidence, without leaking hidden content.

### Required tests

- Exact boundary, one-token overflow and output-reserve cases.
- Different tokenizers/templates for Kimi and DeepSeek.
- Model fallback after preparation.
- Tool/schema overhead and reasoning-budget accounting.
- Restart after compaction and before model dispatch.
- Corrected source material invalidates stale context/cache entries.
- Restricted content never enters another tenant's context.

### Exit gate

Ryuk can resume a conversation and safely construct different bounded contexts for two candidate deployments. Fallback never relies on another model's token accounting.

## Phase 5 — Implement the authorized tool and coding sandbox boundary

### Objective

Allow models to propose coding actions while Ryuk retains permission and execution control.

### ADR first

Define tool capability grants, effect classifications, approval policy, sandbox isolation, network/secret access, idempotency and artifact lineage.

### Steps

1. Define typed tool declarations and validated invocation proposals separately from tool execution.
2. Bind allowed tools, paths, network destinations, environment variables, time/CPU/memory/output limits and approval requirements to each task.
3. Build an isolated repository workspace from a pinned base revision. Do not let parallel model tasks mutate the same checkout.
4. Limit filesystem access and prevent credentials from entering model-visible context, command output or artifacts.
5. Validate arguments deterministically before execution; never execute partial streamed arguments.
6. Record invocation intent, idempotency key, approval, start, bounded output, exit condition and reconciled effect.
7. Run formatters/tests as explicit tools and store results as source-linked artifacts.
8. Represent changes as patches or commits tied to the base revision.
9. Apply/integrate accepted patches under coordinator control and rerun checks on the integrated revision.
10. Block or require explicit approval for destructive, externally visible or otherwise high-impact tools.

### Required tests

- Path traversal, symlink escape, command injection and secret exfiltration attempts.
- Timeout, output flood, process-tree cleanup and cancellation.
- Duplicate side-effect proposal and ambiguous external outcome.
- Patch conflict and stale-base rejection.
- Parallel isolated workspaces and cleanup.
- Malicious tool request from retrieved text or reviewer output cannot grant authority.

### Exit gate

A model-generated patch can be tested and integrated without the model gaining direct repository, network, credential or policy authority.

## Phase 6 — Deliver the bounded Kimi–DeepSeek coding workflow

### Objective

Implement the user's initial multi-model collaboration using explicit workflows, measurable routing and bounded review.

### Steps

1. Define coding task types: interpret, locate, implement, test, repair, review and synthesize.
2. Define handoff packets containing objective, pinned sources, accepted artifacts, allowed tools, expected output, acceptance tests, unresolved questions and remaining budget.
3. Begin with deterministic templates:
   - Kimi for screenshot/multimodal interpretation.
   - Kimi or DeepSeek for implementation based on verified eligibility and measured task profile.
   - Sandboxed deterministic tests after every proposed integrated patch.
   - Optional independent review only for configured risk/uncertainty triggers.
4. Bind reviewer findings to the exact target artifact digest and generator identity.
5. Run deterministic checks before model review.
6. Keep audit and evaluation separate. The reviewer emits findings; policy chooses accept, bounded repair, reroute or escalation.
7. Prohibit recursive review of review tasks and enforce a shared default loop bound consistent with ADR-008.
8. Route repair with failing tests and relevant findings, not the entire uncontrolled transcript.
9. Produce a final synthesis only from accepted artifacts and verification evidence.
10. Record why one model, both models or a reviewer was selected.

### Evaluation experiment

Compare:

- Kimi only.
- DeepSeek only.
- Policy-selected single model.
- Policy-selected implementation plus triggered review.
- Always use both models as a cost/latency control, not the expected winner.

Measure accepted-patch rate, regression rate, wall time to accepted result, calls, tokens/cost, repair count, reviewer defect yield, false rejects and unresolved escalations. Tests decide acceptance; agreement is not proof.

### Exit gate

Selective orchestration demonstrates a documented benefit or justified tradeoff over a single-model baseline. If it does not, retain the simpler workflow and do not promote costly cross-review by default.

## Phase 7 — Add scoped persistent memory and retrieval

### Objective

Remember useful facts, decisions and preferences with provenance without confusing conversation history, vector indexes or cache state with truth.

### ADR first

Approve memory scopes, consent/write policy, source authority, conflict resolution, expiry, correction, deletion, export, retention and rebuild semantics.

### Steps

1. Define `MemoryScope`, `MemoryItem`, `MemoryEvidence`, `ContentRecord`, `EmbeddingSpace` and `EmbeddingRecord` contracts.
2. Default to project-scoped memory; make cross-project sharing opt-in and user preferences explicit.
3. Store original authorized content and immutable source revisions before derived indexes.
4. Implement candidate extraction followed by deterministic secret/sensitivity filtering and policy-controlled commit. Do not automatically save every interaction.
5. Require evidence links and record whether a claim is user-stated, measured, source-derived or model-hypothesized.
6. Implement correction/supersession and expiry; keep audit metadata without continuing to retrieve invalid claims.
7. Add lexical retrieval first, then one versioned embedding space and optional rerank task through ordinary adapters.
8. Filter by authorized scope before search and recheck source access before context assembly.
9. Rebuild indexes from source records; use blue/green index migration when changing embedding profiles.
10. Propagate deletion and permission changes to memory visibility, embeddings, caches and retained context snapshots according to policy.
11. Add user-facing inspect, correct, forget and export operations.
12. Evaluate third-party/NeMo memory providers only as optional adapters behind these contracts.

### Required tests

- Cross-tenant/project retrieval attacks.
- Stale and contradictory memories.
- Correction and source-revision changes.
- Deletion before and after backup/restore.
- Embedding-space mismatch and query/passage mode errors.
- Prompt injection embedded in retrieved content.
- Retrieval quality versus no-memory and full-history baselines.

### Exit gate

Memory improves the selected workload while meeting isolation, evidence, correction and deletion requirements. A vector hit alone is never treated as verified truth.

## Phase 8 — Integrate specialist modalities one vertical slice at a time

### Objective

Use specialist NVIDIA candidates for speech, document extraction, visual understanding, retrieval and video without forcing their protocols into one chat abstraction.

### Recommended order

1. Text embeddings and reranking, because Phase 7 needs evaluated retrieval.
2. OCR plus page/table/graphic structure as one document-ingestion workflow.
3. Parakeet ASR for audio ingestion.
4. General image interpretation alternatives.
5. Cosmos video understanding after its exact hosted/self-hosted contract is verified.
6. Safety classification as an additional signal, never an authorization boundary.

### Steps for each specialist

1. Recheck current official API/model documentation and license/access terms.
2. Create a distinct typed task/result contract and deployment capability profile.
3. Preserve source coordinates, timestamps, page/region structure and confidence/evidence fields as applicable.
4. Enforce file type, size, duration/frame/page, fetching and data-residency policies.
5. Normalize typed failures and usage/provenance.
6. Create a representative labeled corpus and deterministic acceptance metrics.
7. Add the specialist as a workflow step only after contract and quality gates pass.
8. Keep unknown and unsupported combinations explicit; do not emulate them silently with a chat model.

### Exit gates by modality

- Retrieval: recall/ranking improves over lexical baseline without isolation failure.
- Documents: OCR/layout/table/graphic outputs retain source geometry and meet task-specific accuracy thresholds.
- ASR: word error and timestamp quality meet the chosen recording/language workload.
- Image/video: responses are source-linked and beat or complement Kimi on selected tasks.
- Safety: incremental detection value is measured, false-positive policy is defined, and no authority depends solely on the classifier.

## Phase 9 — Add conservative caching and improve routing from evidence

### Objective

Reduce cost and latency without compromising tenant isolation, provenance, freshness or side-effect semantics.

### Steps

1. Approve cache semantics for embeddings, retrieval, deterministic tool results and safe inference results separately.
2. Include scope/access epoch, source revisions, model/deployment/profile, preparation fingerprint, generation/reasoning settings, tools, schema and validator versions in keys where relevant.
3. Preserve original provenance on reuse and record a separate cache-reuse event.
4. Send cached results through current validation/evaluation policy.
5. Initially exclude repository mutations, personalized/private outputs and side-effecting tasks from semantic answer caching.
6. Add invalidation for source, policy, permission, memory, model profile and validator changes.
7. Keep serving KV-cache behavior under the serving runtime; never expose it as durable memory.
8. Train no online self-modifying router. Use versioned offline evaluation, reviewed policy promotion, canaries and rollback.
9. Add uncertainty/freshness to routing evidence and minimum sample requirements.
10. Revisit Dynamo only with comparable direct/aggregated/disaggregated benchmark records and existing ADR thresholds.

### Required tests

- Cross-scope cache key collision.
- Stale source/policy/profile invalidation.
- Cache hit has correct original provenance and no fabricated model attempt.
- Side effects never replay from cache.
- Routing replay is deterministic for a pinned evidence/policy version.
- Canary regression triggers rollback.

### Exit gate

Caching or new routing policy produces measured benefit with no correctness, isolation, quality or reliability regression.

## Phase 10 — Introduce distributed production infrastructure only when required

### Objective

Support controller replicas and production scale without weakening transactional workflow and quota semantics.

### Trigger

Begin only after measured availability/throughput requirements exceed a single-controller architecture or production HA is required.

### Steps

1. Select a transactional production database and migration strategy implementing the existing store contracts.
2. Implement tenant-qualified indexes, immutable events, idempotency, leases/fencing and backup-safe deletion metadata.
3. Select distributed admission/quota coordination; prove consistency under concurrency and partitions.
4. Add an external queue only if needed; use transactional outbox/inbox and duplicate-tolerant workers.
5. Store artifacts in encrypted, versioned object storage with access checks and integrity digests.
6. Deploy external secret management with rotation and revocation.
7. Add deployment lifecycle, signature/attestation, SBOM and vulnerability gates.
8. Implement encrypted backups, point-in-time recovery where required, index rebuild and tombstone reconciliation.
9. Deploy metrics, traces and safe logs with alerting and runbooks.
10. Test rolling upgrade and schema compatibility across controller/worker versions.

### Exit gate

Multiple controllers preserve quotas, transitions and tenant isolation during duplicate delivery, node loss, database failover and network partitions. Restore meets demonstrated RPO/RTO.

## Phase 11 — Production certification and controlled rollout

### Objective

Prove the complete system under realistic load and failure before calling the first slice production-ready.

### Steps

1. Define SLIs/SLOs for availability, accepted-result latency, deadline success, correctness proxies, queueing, errors, capacity, failover and recovery.
2. Load test concurrency, quotas, context preparation, model endpoints, database and artifact paths.
3. Soak test for connection, memory, task, worker, database and telemetry leaks.
4. Chaos test worker loss, endpoint overload, stale health, interrupted networks, record-store loss and partial recovery.
5. Perform restore drills and reconcile workflows, permissions, tombstones, indexes and caches.
6. Rotate credentials and signing material under load.
7. Run red-team tests for prompt injection, cross-tenant references, tool escape, secret leakage and poisoned memory.
8. Run the held-out coding/context/memory/specialist evaluation suite.
9. Conduct a limited canary with feature flags, rollback, incident owner and support runbook.
10. Publish a production evidence report listing all unsupported or unverified features.

### Exit gate

All first-slice requirements in `PROJECT_STATUS_REPORT.md` pass on the intended deployment. No mock can run; results have truthful identity and attempts; security, recovery and policy promotion are demonstrated rather than configured only.

## 4. Cross-phase test program

Maintain the following suites as first-class versioned assets:

| Suite | Starts | Purpose |
| --- | --- | --- |
| Core contract and property tests | Phase 0 | Domain invariants, state transitions, policy determinism |
| Adapter contract fixtures | Phase 2 | External protocol/profile semantics and failure normalization |
| Workflow recovery matrix | Phase 3 | Crash boundaries, duplicates, leases, cancellation |
| Context evaluation corpus | Phase 4 | Fitting, retrieval, compaction and model switching |
| Tool/sandbox adversarial suite | Phase 5 | Authority, isolation, resource and side-effect safety |
| Coding benchmark | Phase 6 | Kimi/DeepSeek routing and review value |
| Memory evaluation corpus | Phase 7 | Recall, evidence, corrections, deletion and isolation |
| Modality-specific corpora | Phase 8 | ASR/OCR/layout/retrieval/image/video quality |
| Performance and chaos suite | Phase 9 onward | Cache, load, failure, restore and rollout evidence |

No benchmark result is valid without exact model/profile, endpoint/runtime version, workload revision, sampling/reasoning settings, concurrency, cache state, sample count and infrastructure context.

## 5. Change-set strategy

Each phase should normally land through multiple small changes:

1. ADR and contracts.
2. Store/adapter implementation behind a feature flag.
3. Unit and contract tests.
4. API/workflow integration.
5. Integration and failure tests.
6. Evaluation report and documentation.
7. Controlled enablement.

Database migrations must have forward compatibility and a tested rollback or roll-forward procedure. Never deploy a schema that old workers can corrupt during a rolling update.

## 6. Dependencies and work that can safely overlap

The following research may run in parallel without changing the implementation order:

- Phase 2 endpoint contract research and benchmark-corpus preparation.
- Phase 4 context-evaluation corpus design while Phase 3 is implemented.
- Phase 5 sandbox threat modeling before the tool gateway exists.
- Phase 7 retention/governance decisions and retrieval corpus preparation.
- Phase 8 labeled specialist datasets and license/access review.

Do not parallelize code that defines the same core contracts or database schema. Do not have multiple model workers edit one checkout. Infrastructure research does not waive the preceding exit gate.

## 7. Decisions needed from the product owner

Resolve these before the phase that depends on them:

| Decision | Needed before |
| --- | --- |
| Hosted vs self-hosted first deployments and authorized credentials | Phase 2 integration |
| Acceptable identity evidence for opaque hosted endpoints | Phase 2 activation |
| Workflow token/cost/time/task/retry/review budgets | Phase 3 |
| Automatic vs approval-required repository/tool actions | Phase 5 |
| Retention, sensitivity exclusions, sharing and deletion policy | Phase 7 |
| Initial benchmark tasks and acceptance thresholds | Phases 2 and 6 |
| Single-controller vs HA production target and RPO/RTO | Phase 10 |

Until decided, implement interfaces and safe defaults but do not invent authorization or production policy.

## 8. Immediate next development change set

The immediate implementation unit should be **Phase 0 plus the first vertical portion of Phase 1**, not orchestration or memory.

1. Reproduce the current full validation suite from a clean checkout.
2. Produce the public route/enforcement matrix.
3. Add failing API tests proving inference/audit paths currently require the desired principal, role and quota semantics.
4. Wire the smallest shared authentication/authorization/admission dependency.
5. Persist a sanitized terminal record for one governed inference route.
6. Verify quota rejection never contacts an adapter and permits are always released.
7. Run all validation and inspect the complete diff.

Stop after this change set and review the evidence. Do not add the workflow schema until API-wide authority and accounting semantics are agreed and tested.

## 9. Definition of done for the plan

This plan is complete only when each phase has an owner, tracked issues, approved decisions, versioned tests/evaluations and stored exit evidence. Completing code tasks without the phase's failure, security and recovery tests does not satisfy the gate.

The intended outcome is not “many models were connected.” It is that Ryuk can make bounded, explainable, recoverable and authorized use of replaceable models while retaining truthful provenance and measurable quality.
