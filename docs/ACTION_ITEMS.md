# Ryuk Action Tracker

**Last updated:** 2026-09-09
**Current milestone:** Phase 2A — offline deployment-profile preparation
**Planning authority:** `RYUK_DEVELOPMENT_PHASE_PLAN.md`

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
| P2A-003 | BLOCKED | Define the hosted identity-evidence acceptance policy | DEC-005 | Policy distinguishes configured, observed, verified, and unavailable evidence |
| P2A-004 | DONE | Add sanitized contract fixtures for both profiles | P2A-001, P2A-002 | Versioned fixtures under `tests/fixtures/phase2a/`; 12 fixture contracts cover linkage, sanitization, identity, success/usage, response limits, malformed output, overload, and timeout; full suite 213 passed |
| P2A-005 | DONE | Complete adapter-local request and response translations for both profiles | P2A-004 | Exact profile allowlist, model-specific reasoning requests, typed answer/reasoning separation, sanitized malformed-reasoning failures, and router preservation; `docs/integrations/nvidia-hosted-nim-compatibility.md`; full suite 216 passed |
| P2A-006 | READY | Add offline cross-deployment failure and provenance tests | P2A-002, P2A-005 | Failed primary and successful fallback attempts preserve exact deployment/model provenance |
| P2A-007 | BLOCKED | Record the Phase 2A review and readiness decision | P2A-001 through P2A-006 | Review report lists passed checks, unknowns, and explicit Phase 2B blockers |

## Product-owner decisions

These decisions block external Phase 2B work. Do not infer authorization from
the existence of configuration fields or integration tests.

| ID | Status | Decision needed | Required record |
| --- | --- | --- | --- |
| DEC-001 | BLOCKED | Choose hosted-first or self-hosted-first | Decision, rationale, date, and approved deployment environments |
| DEC-002 | BLOCKED | Approve exact initial models or substitutes | Exact model names and acceptable revisions |
| DEC-003 | BLOCKED | Define data classification, residency, retention, and provider-disclosure constraints | Versioned policy referenced by deployment profiles |
| DEC-004 | BLOCKED | Approve credentials, secret mechanism, hardware, and budget | Authorized access path; no credential values committed |
| DEC-005 | BLOCKED | Define acceptable identity evidence for opaque hosted endpoints | Minimum evidence required for activation and attribution |
| DEC-006 | BLOCKED | Select benchmark repositories/tasks and acceptance thresholds | Pinned revisions, metrics, thresholds, and evaluation owner |

## Phase 2B — real deployment certification

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| P2B-001 | BLOCKED | Provision or identify the two exact authorized endpoints | DEC-001 through DEC-005, P2A-007 | Endpoint inventory with secret references and no secret values |
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
| WF-001 | BLOCKED | Approve a workflow-state ADR | P2A-007 | States, transitions, transactions, leases, fencing, idempotency, cancellation, and uncertain effects specified |
| WF-002 | BLOCKED | Implement tenant-scoped workflow, task, event, and artifact records | WF-001 | Migrations and invariant tests |
| WF-003 | BLOCKED | Implement atomic ready-task claiming with leases and fencing | WF-002 | Duplicate/stale-worker concurrency tests |
| WF-004 | BLOCKED | Allocate one workflow deadline and budget through router attempts | WF-002 | Tests prove nested retries cannot multiply the budget |
| WF-005 | BLOCKED | Dispatch one inference task and bind every attempt/result to workflow state | WF-003, WF-004 | End-to-end single-task workflow contract |
| WF-006 | BLOCKED | Implement deterministic validation before task acceptance | WF-005 | Inference success and accepted task state remain distinct |
| WF-007 | BLOCKED | Implement restart recovery and uncertain-call reconciliation | WF-005 | Crash-before/after-dispatch and lease-expiry tests |
| WF-008 | BLOCKED | Add create, status, cancel, and result APIs with tenant authorization | WF-005 through WF-007 | API, replay, cancellation, and tenant-isolation tests |

## Control-plane hardening

| ID | Status | Action | Dependency | Completion evidence |
| --- | --- | --- | --- | --- |
| CP-002 | READY | Specify terminal-record failure semantics | None | ADR or policy states whether response completion requires record commit |
| CP-003 | BLOCKED | Implement and test the selected terminal-record failure behavior | CP-002 | Failure injection covers successful inference, original failure, and duplicate terminal records |
| CP-004 | READY | Replace shallow event redaction with typed allowlisted events or recursive structural sanitization | None | Nested secret, authorization, prompt, output, and alternate-key tests |
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
