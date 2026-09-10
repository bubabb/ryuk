# Ryuk Next-Session Handoff

**Updated:** 2026-09-09
**Branch:** `main`
**Implementation HEAD before this handoff:** `5d307c7`
**Next action:** `P2A-006` — offline cross-deployment failure and provenance tests

## Completed and verified

Phase 0 and Phase 1 are complete for the current public API surface.

- Recorded the reproducible repository/environment baseline, API enforcement
  matrix, deployment evidence inventory, ADR traceability, and prioritized gaps.
- Made `/health` explicitly public and governed every other current route with
  server-owned API-key identity, tenant/role authorization, and admission.
- Added safe 401/403/429 mappings and proved quota rejection does not contact an
  inference adapter.
- Guaranteed permit release across successful and failed current request paths.
- Added tenant-scoped, sanitized terminal records and redacted lifecycle events.
- Added hashed server-side API-key configuration, expiry/revocation, environment
  secret references at the NIM adapter boundary, and production startup gates.
- Production rejects mock, inline provider credentials, missing durable/control
  configuration, absent eligible deployments, and unverified deployment identity.
- Made local admission and SQLite records thread-safe.
- Migrated execution records to append-oriented schema v2; schema v1 is upgraded
  without data loss and reused correlation IDs no longer break completed calls.
- Tracked the proposed architecture and phase-plan documents. Their status remains
  `Proposed`; tracking them is not production certification.

Final verification at handoff:

```text
180 passed, 4 skipped, 1 warning
compileall: passed
Ruff: passed
Mypy: passed across 73 backend/test/script files
routing evaluation: accepted
audit evaluation: accepted
git diff --check: passed
```

## Distributed control-plane foundation added after the prior handoff

The distributed control-plane change set adds implementations needed by the later Phase 10 gate,
without claiming that Phase 10 itself is complete:

- PostgreSQL-backed, append-oriented, tenant-scoped execution records.
- Redis-backed atomic request, token, and concurrency admission.
- Production startup checks for active credentials, tenant quotas, and healthy
  distributed record/admission dependencies.
- Vault KV secret resolution with TLS-only production configuration.
- Fail-closed deployment activation evidence and stronger artifact manifest
  validation.
- Tenant headers are constraints only and cannot override authenticated identity.
- Local PostgreSQL and Redis integration runners and real-service contracts.

Review corrections made on 2026-09-09 include closing partially initialized
resources, cleanup on application startup failure, and preventing Redis quota
keys from expiring while a request permit is active. The real Redis contention
test proves the configured concurrency ceiling across multiple clients.

Verified on 2026-09-09:

```text
PostgreSQL real-service contracts: passed
Redis real-service contracts, including contention: passed
Full unit/contract suite with local PostgreSQL/Redis: 199 passed, 5 external-service skips
Ruff: passed
Mypy: passed across 74 backend/test/script files
compileall: passed
routing evaluation: accepted
audit evaluation: accepted
git diff --check: passed
```

This is implementation evidence, not production certification. Redis permits
intentionally fail closed after a controller crash and still need an explicit
lease/reconciliation design. Network-partition semantics, backup/restore RPO/RTO,
Vault rotation/revocation, multi-replica chaos tests, and operational runbooks
remain Phase 10 exit work.

The external-service skips require real Dynamo, NIM, hosted NVIDIA NIM, SGLang,
and vLLM services. No real external model was integration-tested,
benchmark-evaluated, or production-certified.

## Phase 2A progress completed on 2026-09-09

- Researched and pinned the exact hosted identifiers `moonshotai/kimi-k3` and
  `deepseek-ai/deepseek-v4-flash-0731` without making external inference calls.
- Added immutable, production-ineligible offline deployment profiles that keep
  unavailable hosted identity evidence explicit.
- Added sanitized, versioned fixtures for identity, success and usage, response
  limits, malformed output, overload, and timeout behavior.
- Implemented an exact hosted-model allowlist and profile-specific request
  translations, including the two different reasoning-control shapes.
- Added typed answer/reasoning separation, normalized hosted reasoning output,
  sanitized malformed-reasoning failures, and router preservation.
- Replaced deprecated Starlette `TestClient` usage with HTTPX's in-process ASGI
  transport while retaining API coverage.

Final verification for the implementation HEAD:

```text
Full unit/contract suite: 216 passed, 8 external-service skips
Starlette deprecation warning promoted to error: passed
Ruff: passed
Mypy: passed
compileall: passed
git diff --check: passed
```

The Phase 2A work is not external deployment certification. No credentials,
protected data, or provider response headers were committed, and no hosted
profile is eligible for production activation.

## Open work

The next planned work is to finish the offline Phase 2A gate. Other open work
remains ordered behind the plan rather than being implicitly authorized.

1. Implement `P2A-006`: prove failed-primary/successful-fallback behavior and
   exact deployment/model provenance entirely offline.
2. Complete `P2A-007`: record the Phase 2A review, unknowns, and readiness
   decision. Keep `P2A-003` blocked until `DEC-005` defines acceptable hosted
   identity evidence.
3. Obtain the product-owner decisions `DEC-001` through `DEC-006` before any
   Phase 2B provider contact, account change, protected-data transfer, or spend.
4. Certify the two exact real deployments only after those decisions and the
   Phase 2A review are complete.
5. Complete Vault authentication/rotation/revocation drills; the current KV
   resolver is an implementation boundary, not operational certification.
6. Implement streaming and disconnected-client cancellation as its own vertical
   slice; this is where disconnected-stream permit tests belong.
7. Before multi-replica production, complete Redis permit reconciliation and
   prove PostgreSQL backup/restore, partition behavior, and RPO/RTO.
8. Complete supply-chain, load/soak/chaos, observability, incident-response, and
   production-certification gates in their planned phases.

Do not begin Phase 3 workflow schema work until the Phase 2 exit evidence is
recorded, unless the project owner deliberately changes the approved order.

## Product-owner decisions required before Phase 2 integration

- Hosted-first or self-hosted-first deployment strategy.
- Authorized credentials and permissible secret-management mechanism.
- Data classification, residency, and provider-disclosure constraints.
- Available hardware and infrastructure budget; Phase 2 does not authorize a
  purchase or external-account change.
- Acceptable identity evidence for hosted endpoints whose artifact digest,
  runtime, or hardware is opaque.
- Initial benchmark repositories/tasks and acceptance thresholds.

## Exact next-session starting procedure

1. Work in `/home/sudosu/projects/ryuk`.
2. Read `AGENTS.md`, this handoff, `docs/ACTION_ITEMS.md`,
   `RYUK_ARCHITECTURE_DESIGN.md`, and Phase 2 of
   `RYUK_DEVELOPMENT_PHASE_PLAN.md`.
3. Confirm `git status` is clean and local `main` matches `origin/main`.
4. Run the documented validation in the `ryuk-ai` Python 3.12 environment.
5. Confirm the Phase 2 product-owner decisions above before contacting real
   providers, changing accounts, purchasing resources, or sending protected data.
6. Start with `P2A-006`; use the existing immutable profiles and sanitized
   fixtures to test primary failure, fallback success, attempt ordering, and
   exact deployment/model provenance.
7. Review the implementation and run focused tests, then the full validation
   suite. Update `docs/ACTION_ITEMS.md` in the same change set.
8. Complete `P2A-007` after `P2A-006`, explicitly recording that `P2A-003` and
   Phase 2B remain blocked by the product-owner decisions.
9. Do not contact providers or begin real certification without the required
   authorization. Do not begin Phase 3 workflow implementation before the
   Phase 2A review unless the project owner deliberately changes the order.

## Repository safety

- `llms.md` is tracked, owner-controlled, and unchanged by Phase 0/1.
- No plaintext credential belongs in Git, logs, records, fixtures, or reports.
- Mock remains development/test-only and is prohibited in production.
- Unknown external capabilities, costs, limits, and identity details remain
  `Unknown` until exact-boundary evidence exists.
