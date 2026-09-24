# Ryuk Action Tracker

**Last updated:** 2026-09-24
**Current milestone:** Offline Phase 3 exit review
**Planning authority:** `RYUK_DEVELOPMENT_PHASE_PLAN.md`
**Next session starts with:** WF-009 Phase 3 exit review and remaining scope reconciliation; see `docs/NEXT_SESSION_HANDOFF.md`; live certification remains pending by owner instruction

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

Owner scope update (2026-09-15): continue offline first and leave live certification pending. Use synthetic/public data only, no private repositories, and treat catalog identity as observed rather than artifact-verified.

The remaining decisions block external Phase 2B work. Do not infer authorization from
the existence of configuration fields or integration tests.

| ID | Status | Decision needed | Required record |
| --- | --- | --- | --- |
| DEC-001 | HOLD | Choose hosted-first or self-hosted-first | Decision, rationale, date, and approved deployment environments |
| DEC-002 | HOLD | Approve exact initial models or substitutes | Exact model names and acceptable revisions |
| DEC-003 | REVIEW | Define data classification, residency, retention, and provider-disclosure constraints | Synthetic/public-only inputs and no private repositories approved; live residency/provider/retention requirements remain pending |
| DEC-004 | HOLD | Approve credentials, secret mechanism, hardware, and budget | Authorized access path; no credential values committed |
| DEC-005 | DONE | Define acceptable identity evidence for opaque hosted endpoints | Owner accepted observed catalog attribution for synthetic/public offline work; no artifact verification claim; live activation policy remains DEC-007 |
| DEC-006 | HOLD | Select benchmark repositories/tasks and acceptance thresholds | Pinned revisions, metrics, thresholds, and evaluation owner |
| DEC-007 | HOLD | Approve identity evidence for live hosted activation | Offline catalog observation is accepted; live-use acceptance requires a separate decision when certification resumes |

## Phase 2B — real deployment certification

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| P2B-001 | BLOCKED | Provision or identify the two exact authorized endpoints | DEC-001 through DEC-005, DEC-007, P2A-007 | Endpoint inventory with secret references and no secret values |
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
| WF-009 | READY | Record the offline Phase 3 exit review and reconcile remaining scheduler, startup recovery, cancellation propagation, and cost/task-budget scope against the phase plan | WF-001 through WF-008 | Explicit implemented/deferred evidence and stable follow-up IDs before Phase 4 advancement; no production or live certification implied |

## Control-plane hardening

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| CP-002 | DONE | Specify terminal-record failure semantics | None | `docs/adr/ADR-009-terminal-record-failure-semantics.md`: commit before success; preserve original failure; no automatic replay after uncertain commit |
| CP-003 | DONE | Implement and test the selected terminal-record failure behavior | CP-002 | API fault-injection tests cover success/original failure, permit release, reused correlation IDs and commit with lost acknowledgement |
| CP-004 | DONE | Replace shallow event redaction with typed allowlisted events or recursive structural sanitization | None | Scalar operational field allowlist; nested secret/authorization/prompt/output, alternate-key, object, control-character, and invalid-count contracts in `tests/test_control_plane.py` |
| CP-005 | HOLD | Add Redis permit leases/fencing and process-crash reconciliation | Phase 10 trigger | No silent capacity reopening; recovery behavior proven across controller death |
| CP-006 | HOLD | Prove PostgreSQL migrations, backup/restore, and RPO/RTO | Phase 10 trigger | Concurrent migration and scheduled restore reports |
| CP-007 | HOLD | Prove Redis/database behavior under failover and partitions | Phase 10 trigger | Multi-replica chaos report with quota and tenant invariants |
| SEC-001 | HOLD | Add Vault workload authentication, renewal, rotation, and revocation drills | Production deployment design | Drill report without stored or logged secret material |

## Later phase gates

| ID | Status | Action | Dependency |
| --- | --- | --- | --- |
| CTX-001 | HOLD | Approve context-preparation ADR and implement candidate-specific token fitting | Phase 3 exit |
| TOOL-001 | HOLD | Approve authorized tool/sandbox ADR and implement one isolated coding action | Phase 4 exit |
| COLLAB-001 | HOLD | Implement the bounded Kimi–DeepSeek coding workflow | Phase 2 and Phase 5 exits |
| MEM-001 | HOLD | Approve source/evidence/deletion ADR and add scoped persistent memory | Phase 6 exit |
| SPEC-001 | HOLD | Add specialist modalities one complete vertical slice at a time | Phase 7 exit |
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
