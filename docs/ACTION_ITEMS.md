# Ryuk Action Tracker

**Last updated:** 2026-09-26
**Current milestone:** Product decisions and full-project completion sequencing
**Planning authority:** `RYUK_DEVELOPMENT_PHASE_PLAN.md`
**Next session starts with:** P2B-001 is READY: inventory the two exact NVIDIA Developer Program endpoints and a secret reference without recording the credential; free resources only, USD 0 paid-spend ceiling, synthetic/public data, and stop on absent entitlement or any payment requirement

Model assignments and cost-saving review: [MODEL_TASK_ALLOCATION.md](MODEL_TASK_ALLOCATION.md). Assignments preserve every existing authorization and phase gate.

This is the operational task list for Ryuk. Update it in the same change set as
the work it tracks. Architecture documents explain why; this file records what
must happen next and what evidence closes each item.

## Status legend

- `READY` — sufficiently specified and not blocked.
- `IN PROGRESS` — actively being implemented; include the branch or change-set note.
- `BLOCKED` — requires a named decision, credential, service, or predecessor.
- `REVIEW` — implementation exists but its closing evidence is incomplete.
- `DONE` — acceptance evidence exists and is linked or named.
- `HOLD` — deliberately deferred until its trigger is satisfied.

An item is not `DONE` merely because code exists. Tests, documentation, and any
required real-system evidence must also exist.

## Current focus

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| DOC-001 | DONE | Establish a consolidated current architecture and phase review | None | `docs/RYUK_PROJECT_AND_PHASE_REVIEW_2026-09-09.md`; commit `508a1c0` |
| CP-001 | DONE | Harden the distributed control-plane foundation | None | PostgreSQL and Redis real-service contracts; commit `907f7e8` |
| QA-001 | DONE | Resolve the Starlette `TestClient`/httpx deprecation warning without reducing API coverage | None | API tests use HTTPX's in-process ASGI transport; 31 API tests passed with `StarletteDeprecationWarning` promoted to an error |
| P2A-001 | DONE | Verify the current official contracts and exact public identifiers for Kimi K3 and DeepSeek V4 or approved substitutes | Product model choice | `docs/research/phase-2a-model-contracts-2026-09-09.md`; NVIDIA hosted candidates pinned as `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4-flash-0731` |
| P2A-002 | DONE | Define one immutable offline deployment profile for each selected model | P2A-001 | Frozen schema and validated manifests under `deployments/offline/`; unknown hosted runtime, hardware, image digest, artifact digest, and cancellation evidence remain explicit |
| P2A-003 | DONE | Define the hosted identity-evidence acceptance policy | DEC-005 | ADR-010 technical semantics tested; owner accepted synthetic/public-only offline scope and observed catalog identity on 2026-09-15; live activation excluded |
| P2A-004 | DONE | Add sanitized contract fixtures for both profiles | P2A-001, P2A-002 | Versioned fixtures under `tests/fixtures/phase2a/`; 12 fixture contracts cover linkage, sanitization, identity, success/usage, response limits, malformed output, overload, and timeout; full suite 213 passed |
| P2A-005 | DONE | Complete adapter-local request and response translations for both profiles | P2A-004 | Exact profile allowlist, model-specific reasoning requests, typed answer/reasoning separation, sanitized malformed-reasoning failures, and router preservation; `docs/integrations/nvidia-hosted-nim-compatibility.md`; full suite 216 passed |
| P2A-006 | DONE | Add offline cross-deployment failure and provenance tests | P2A-002, P2A-005 | `tests/test_phase2a_failover.py`: 16 offline cases pass; deployment IDs map to exact models in the test registry and fallback result provenance is preserved; historical snapshots tracked by P2A-008 |
| P2A-007 | DONE | Record the Phase 2A review and readiness decision | P2A-001 through P2A-006 | Offline readiness accepted under owner scope update; `docs/reports/phase-2a-review-2026-09-15.md`; no live certification claimed |
| P2A-008 | DONE | Preserve immutable per-attempt deployment/model attribution for historical replay | P2A-006 | Attempt schema v2, JSON replay with v1 compatibility, API persistence on success/failure, and SQLite reopen/registry replacement tests in `tests/test_attempt_history.py` and `tests/test_api.py` |

## Product-owner decisions

Owner scope update (2026-09-26): the intended product may support all data
classifications, but current offline development and provider checks remain
synthetic/public-only until DEC-003's approved governance controls are
implemented and the applicable tenant/provider evidence is verified. Treat
catalog identity as observed rather than artifact-verified.

The remaining decisions block external Phase 2B work. Do not infer authorization from
the existence of configuration fields or integration tests.

| ID | Status | Decision needed | Required record |
| --- | --- | --- | --- |
| DEC-001 | DONE | Choose hosted-first or self-hosted-first | Owner approved hosted-first on 2026-09-26: self-managed Ryuk controller with explicitly authorized hosted NVIDIA inference endpoints; `docs/decisions/DEC-001-hosted-first-initial-release.md` |
| DEC-002 | DONE | Approve exact initial models or substitutes | Owner approved exact initial catalog IDs `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4-flash-0731` on 2026-09-26; live availability and served revisions remain gated; `docs/decisions/DEC-002-initial-hosted-model-targets.md` |
| DEC-003 | DONE | Define data classification, residency, retention, and provider-disclosure constraints | Owner approved all-class product scope, tenant/legal region constraints, mandatory per-class retention/deletion policy, no provider training and explicit provider/model disclosure on 2026-09-26; activation remains evidence-gated; `docs/decisions/DEC-003-data-governance.md` |
| DEC-004 | DONE | Approve credentials, secret mechanism, hardware, and budget | Owner approved NVIDIA Developer Program free resources, protected local environment injection, synthetic/public-only Phase 2B use, and a USD 0 paid-spend ceiling on 2026-09-26; paid expansion requires a separate explicit decision; `docs/decisions/DEC-004-provider-access-deferred.md`; `docs/reports/DEC-004-developer-program-access-review-2026-09-26.md` |
| DEC-005 | DONE | Define acceptable identity evidence for opaque hosted endpoints | Owner accepted observed catalog attribution for synthetic/public offline work; no artifact verification claim; live activation policy remains DEC-007 |
| DEC-006 | DONE | Select benchmark source policy and acceptance thresholds | Owner approved public version-pinned repositories plus synthetic Ryuk tasks, at least 100 held-out matched cases, 87% success, zero critical failures, a 5-point paired noninferiority margin, a 25% all-in savings gate and owner final acceptance on 2026-09-26; exact run sources, revisions, sealed cases and named independent people are correctly deferred to EVAL-010; `docs/decisions/DEC-006-benchmark-policy.md`; `docs/reports/DEC-006-benchmark-policy-review-2026-09-26.md` |
| DEC-007 | DONE | Approve identity evidence for live hosted activation | Owner approved exact configuration/response identity agreement plus independent provider catalog/dashboard mapping and timestamped sanitized endpoint/account evidence on 2026-09-26; mismatches fail closed and claims remain provider-attested, not weight-verified; `docs/decisions/DEC-007-live-hosted-identity.md` |
| DEC-008 | DONE | Select initial-release feature scope | Owner included multi-step workflows, governed tools, persistent memory and caching; deferred collaboration, specialist modalities and HA until after initial certification on 2026-09-26; `docs/decisions/DEC-008-initial-release-feature-scope.md` |

## Phase 2B — real deployment certification

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| P2B-001 | READY | Identify the two exact authorized NVIDIA Developer Program endpoints | DEC-001 through DEC-005, DEC-007, P2A-007 | Endpoint inventory with account-observed free entitlement and secret references but no secret values; stop before payment or paid provisioning |
| P2B-002 | BLOCKED | Verify authentication, readiness, and served-model identity | P2B-001 | Sanitized observations for each exact endpoint |
| P2B-003 | BLOCKED | Measure ordinary generation and safe input/output limits | P2B-001 | Reproducible contract report with model settings and limits |
| P2B-004 | BLOCKED | Exercise timeout, overload, malformed response, and cancellation behavior | P2B-001 | Normalized failure evidence and cancellation/late-result observations |
| P2B-005 | BLOCKED | Verify structured output and tool behavior instead of assuming support | P2B-001 | Per-profile support decision with passing or negative contracts |
| P2B-006 | BLOCKED | Run real cross-deployment failover | P2B-002 through P2B-004 | Both attempts recorded with correct identity, usage, and provenance |
| P2B-007 | BLOCKED | Run the pinned quality/performance/cost benchmark | DEC-006, P2B-003 | Accepted-patch, test-pass, latency, throughput, failure, usage, and cost report |
| P2B-008 | BLOCKED | Approve or reject each deployment profile | P2B-002 through P2B-007 | Signed-off activation decision; unknown/stale hard constraints remain ineligible |

## Phase 3 — durable single-task workflow

These design tasks may proceed after Phase 2A. Production activation remains
blocked until Phase 2B passes.

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| WF-001 | DONE | Approve a workflow-state ADR | P2A-007 | ADR-011 defines the offline single-task scope, atomic transitions/events, tenant idempotency, leases/fencing, cancellation, and uncertain execution |
| WF-002 | DONE | Implement tenant-scoped workflow, task, event, and artifact records | WF-001 | TaskPacket v1, ArtifactRef/StoredArtifact, atomic completion, tenant-scoped reads, v1-to-v2 migration and failure rollback; `docs/reports/workflow-packets-artifacts-review-2026-09-15.md` |
| WF-003 | DONE | Implement atomic ready-task claiming with leases and fencing | WF-002 | Two-connection race, packet validation, owner/fence/lease/cancellation checks, and lock-wait-expiry regression pass; 282 offline tests green |
| WF-004 | DONE | Allocate one workflow deadline and budget through router attempts | WF-002 | `WorkflowBudget` and ADR-012 share one monotonic deadline/attempt/output-token budget across router attempts; 286 offline tests pass; `docs/reports/workflow-budget-review-2026-09-15.md` |
| WF-005 | DONE | Dispatch one inference task and bind every attempt/result to workflow state | WF-003, WF-004 | `WorkflowExecutor` binds tenant claim, TaskPacket, one WorkflowBudget, router attempts/provenance, and terminal artifact; `docs/reports/workflow-dispatch-review-2026-09-15.md`; 290 offline tests pass |
| WF-006 | DONE | Implement deterministic validation before task acceptance | WF-005 | ADR-014, artifact-bound durable decisions, replay/tenant/rollback/migration contracts; 316 offline tests pass; `docs/reports/workflow-validation-review-2026-09-23.md` |
| WF-007 | DONE | Implement restart recovery and uncertain-call reconciliation | WF-005, WF-006 | ADR-015 dispatch/outcome journal, fenced recovery, crash/process-exit/concurrency/rollback/migration tests; 330 offline tests pass; `docs/reports/workflow-recovery-review-2026-09-24.md` |
| WF-008 | DONE | Add create, status, cancel, and result APIs with tenant authorization | WF-005 through WF-007 | ADR-016, server-bound acceptance/budgets, four governed routes, replay/cancellation/isolation/quota/migration tests; 359 offline tests pass; `docs/reports/workflow-api-review-2026-09-24.md` |
| WF-009 | DONE | Record the offline Phase 3 exit review and reconcile remaining scope against the phase plan | WF-001 through WF-008 | `docs/reports/phase-3-exit-review-2026-09-25.md`; offline single-task exit criterion met; operational gaps tracked as WF-010–WF-014; no production certification implied |
| WF-010 | DONE | Add a bounded local dispatcher/worker lifecycle for queued workflows | Owner authorized the next bounded offline task on 2026-09-25 | ADR-019, `backend/workflows/dispatcher.py`, four lifecycle/concurrency/failure tests and `docs/reports/workflow-dispatcher-review-2026-09-25.md`; explicit start only, API creation remains non-executing |
| WF-011 | DONE | Orchestrate expired-lease recovery and uncertain-outcome reconciliation at service startup | WF-010; owner authorized the next bounded offline task on 2026-09-25 | ADR-020, atomic bounded recovery, tenant-filtered operator status, restart/failure/rollback tests and `docs/reports/workflow-startup-recovery-review-2026-09-25.md`; no automatic replay |
| WF-012 | HOLD | Add and verify provider cancellation propagation and late-result behavior | P2B-001 through P2B-004 | Per-provider cancellation evidence; no unsupported cancellation claim |
| WF-013 | HOLD | Define durable usage/input-token accounting and monetary cost-budget enforcement | DEC-006 and verified provider usage/billing evidence | Durable counters and enforced policy with explicit unknown-usage behavior |
| WF-014 | DONE | Add task dependency-graph contracts for approved multi-step orchestration | DEC-008 initial-release scope | `backend/workflows/graph.py`, ADR-021, canonical bounded DAG and uncertainty-safe scheduler transitions; `docs/reports/workflow-dependency-graph-contract-review-2026-09-26.md` |
| WF-015 | DONE | Persist graph/node state and atomically release dependency-ready nodes | WF-014 | Schema v6 tenant-scoped graph/node/event records, canonical idempotency, atomic causal transitions, migration/concurrency/restart tests; ADR-022 and `docs/reports/workflow-graph-persistence-review-2026-09-26.md` |
| WF-016 | DONE | Execute graph nodes with artifact handoff and one graph-wide budget | WF-015; existing executor, validation and recovery contracts | Schema v7 fenced claims/artifacts, accepted-only hash-bound dependency envelope, durable aggregate deadline/attempt/output-token budget and no automatic replay; ADR-023 and `docs/reports/workflow-graph-execution-review-2026-09-26.md` |
| WF-017 | DONE | Add governed multi-step create/status/cancel/result APIs and startup recovery | WF-015, WF-016 | ADR-024; schema v8 atomic policy-bound graph admission, authenticated tenant APIs, accepted sink results, fenced cancellation, explicit bounded dispatcher and no-replay startup recovery; `docs/reports/governed-multi-step-workflow-review-2026-09-26.md` |

## Evaluation and model allocation

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| EVAL-001 | DONE | Measure the preregistered 26-task model-allocation pilot v1 and record its decision | Model allocation plan | `docs/reports/model-allocation-pilot-2026-09-25.md`; 23/24 valid scored responses passed, with 1 critical failure, 1 invalid item, and 1 unrun response; gate failed and 87% remains unverified |
| EVAL-002 | DONE | Preregister a corrected pilot v2 without executing model calls | EVAL-001 | Hash-bound `pilot-v2.json` overlay and `PROTOCOL-v2.md`; P02 types explicit, P20 missing/duplicate version-row checks added, infrastructure-only continuation enforced and tested |
| EVAL-003 | DONE | Execute, grade and review the preregistered model-allocation pilot v2 | EVAL-002 | `docs/reports/model-allocation-pilot-v2-2026-09-25.md`; 26/26 passed, zero critical failures or retries; bounded gate passed, population reliability and savings remain unverified |
| EVAL-004 | DONE | Add v3 harness contracts for matched comparison arms, independent-review declarations and non-candidate usage | EVAL-003 | `docs/evaluations/model-allocation-v3-harness.md` and `docs/reports/model-allocation-v3-harness-review-2026-09-25.md`; 15 focused tests; no model calls or v3 benchmark claim |
| EVAL-005 | DONE | Define a blocked-by-default v3 matched-evaluation governance and readiness protocol | EVAL-004 | `v3-governance.json`, fail-closed runner authorization, `docs/evaluations/model-allocation-v3-governance.md`, and review report; no model calls |
| EVAL-006 | DONE | Implement and test the preregistered Newcombe paired noninferiority metric | EVAL-005 | `scripts/model_allocation_statistics.py`, reviewed implementation hash, deterministic published-reference/boundary tests, and `docs/reports/model-allocation-paired-metric-review-2026-09-25.md` |
| EVAL-007 | DONE | Define the sealed held-out case curation contract | EVAL-006 | Case schema, validator/compiler, curation packet, matched grading fixes, and `docs/reports/model-allocation-v3-curation-contract-review-2026-09-26.md`; no cases or calls |
| EVAL-008 | DONE | Define blinded-review and all-in savings evidence contracts | EVAL-007 | Hash-bound review/savings schemas and validators, grader integration, and `docs/reports/model-allocation-v3-review-savings-contract-review-2026-09-26.md`; no external evidence or calls |
| EVAL-009 | DONE | Add unified pre/post-run readiness-bundle validation | EVAL-008 | Bundle/access/approval schemas, cross-bound preflight, runner enforcement, one-attempt ceiling, and `docs/reports/model-allocation-v3-readiness-preflight-review-2026-09-26.md` |
| EVAL-010 | HOLD | Adversarially audit and freeze the offline v3 evaluation protocol and corpus | Offline build-completion gate selected by owner on 2026-09-26 | Exact public repositories and commit hashes, sealed 100-case manifest, named independent curator/reviewer, versioned protocol freeze and trust-chain review; no evaluation execution before the build-completion gate |

## Control-plane hardening

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| CP-002 | DONE | Specify terminal-record failure semantics | None | `docs/adr/ADR-009-terminal-record-failure-semantics.md`: commit before success; preserve original failure; no automatic replay after uncertain commit |
| CP-003 | DONE | Implement and test the selected terminal-record failure behavior | CP-002 | API fault-injection tests cover success/original failure, permit release, reused correlation IDs and commit with lost acknowledgement |
| CP-004 | DONE | Replace shallow event redaction with typed allowlisted events or recursive structural sanitization | None | Scalar operational field allowlist; nested secret/authorization/prompt/output, alternate-key, object, control-character, and invalid-count contracts in `tests/test_control_plane.py` |
| CP-005 | HOLD | Add Redis permit leases/fencing and process-crash reconciliation | Post-initial-release HA scope under DEC-008 | No silent capacity reopening; recovery behavior proven across controller death |
| CP-006 | HOLD | Prove PostgreSQL migrations, backup/restore, and RPO/RTO | Post-initial-release HA scope under DEC-008 | Concurrent migration and scheduled restore reports |
| CP-007 | HOLD | Prove Redis/database behavior under failover and partitions | Post-initial-release HA scope under DEC-008 | Multi-replica chaos report with quota and tenant invariants |
| SEC-001 | HOLD | Add Vault workload authentication, renewal, rotation, and revocation drills | Production deployment design | Drill report without stored or logged secret material |

## Later phase gates

| ID | Status | Action | Dependency |
| --- | --- | --- | --- |
| CTX-001 | DONE | Define context-preparation boundary and implement candidate-specific token fitting | Offline Phase 3 exit review; evidence: ADR-017, `backend/context/`, `docs/reports/context-preparation-review-2026-09-25.md`, 10 focused tests; library only, not wired to dispatch |
| CTX-002 | DONE | Add tenant/project-scoped durable conversations, source records and an authorization-filtered context builder | ADR-018, `backend/context/store.py` and `builder.py`, `docs/reports/conversation-source-store-review-2026-09-25.md`; 9 focused store tests; SQLite offline only, not API-integrated |
| CTX-003 | HOLD | Bind verified candidate tokenizers/templates and capacity evidence to dispatch; account for structured/tool/media overhead | Verified candidate tokenizer/template and Phase 2B contract; reprepare after fallback and prove execution uses the exact counted payload/settings |
| CTX-004 | HOLD | Add source correction/invalidation, checkpoint compaction and context-retention behavior; evaluate critical-fact placement | CTX-002 and CTX-003; approved retention scope; revision-bound invalidation/deletion and held-out evaluation for two candidates |
| TOOL-001 | HOLD | Approve authorized tool/sandbox ADR and implement one isolated coding action | Phase 4 exit |
| COLLAB-001 | HOLD | Implement the bounded Kimi–DeepSeek coding workflow | Post-initial-release scope under DEC-008; Phase 2 and Phase 5 exits |
| MEM-001 | HOLD | Approve source/evidence/deletion ADR and add scoped persistent memory | Phase 6 exit |
| SPEC-001 | HOLD | Add specialist modalities one complete vertical slice at a time | Post-initial-release scope under DEC-008; Phase 7 exit |
| CACHE-001 | HOLD | Add provenance-preserving application result caching | Phase 8 exit |
| PROD-001 | HOLD | Complete load, soak, chaos, restore, observability, incident-response, and rollout certification | All preceding production gates |

## Maintenance rules

When starting work:

1. Change the selected item to `IN PROGRESS`.
2. Add a short note identifying the intended change set when useful.
3. Confirm every dependency is `DONE` or explicitly waived by the product owner.

When finishing work:

1. Run validation proportional to the risk.
2. Record the exact evidence or report that satisfies completion.
3. Change the item to `DONE` only when its completion evidence exists.
4. Add newly discovered work as a new stable ID; do not hide it in prose.
5. Update **Last updated** and **Current milestone**.
6. Keep credentials, protected payloads, and sensitive response headers out of this file.

When plans change, retain completed IDs and mark deliberately deferred work
`HOLD`. Do not renumber existing items; stable IDs allow commits, ADRs, reports,
and test evidence to refer back to the tracker.
