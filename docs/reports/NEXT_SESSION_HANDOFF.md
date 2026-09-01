# Ryuk Next-Session Handoff

**Updated:** 2026-09-01
**Branch:** `main`
**Completed implementation commit:** `163b7597f1cd66c01ba02cf0397dc150fcb59184`

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

The four skips require real Dynamo, NIM, SGLang, and vLLM services. The warning
is the known Starlette TestClient/httpx migration warning. No real external model
was integration-tested, benchmark-evaluated, or production-certified.

## Open work

The next planned gate is Phase 2: certify two exact real deployments. Other open
work remains ordered behind the plan rather than being implicitly authorized.

1. Certify Kimi K3 and DeepSeek V4, or explicitly approved substitutes.
2. Select and integrate a production secret manager beyond the current
   environment-reference implementation; add rotation and revocation drills.
3. Resolve the TestClient/httpx migration warning.
4. Implement streaming and disconnected-client cancellation as its own vertical
   slice; this is where disconnected-stream permit tests belong.
5. Before multi-replica production, replace local SQLite/admission coordination
   with transactional distributed implementations and prove RPO/RTO.
6. Complete supply-chain, load/soak/chaos, observability, incident-response, and
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
2. Read `AGENTS.md`, this handoff, `RYUK_ARCHITECTURE_DESIGN.md`, and Phase 2 of
   `RYUK_DEVELOPMENT_PHASE_PLAN.md`.
3. Confirm `git status` is clean and local `main` matches `origin/main`.
4. Run the documented validation in the `ryuk-ai` Python 3.12 environment.
5. Confirm the Phase 2 product-owner decisions above before contacting real
   providers, changing accounts, purchasing resources, or sending protected data.
6. Inventory the exact selected endpoints and current official contracts.
7. Add separate immutable deployment profiles and sanitized contract fixtures;
   never create a generic NVIDIA-chat profile or save credentials/response headers.
8. Exercise the same versioned core contract for both deployments, then record
   identity, limits, failure behavior, cancellation, usage, and failover evidence.
9. Stop and review the Phase 2 evidence before beginning durable workflows.

## Repository safety

- `llms.md` is tracked, owner-controlled, and unchanged by Phase 0/1.
- No plaintext credential belongs in Git, logs, records, fixtures, or reports.
- Mock remains development/test-only and is prohibited in production.
- Unknown external capabilities, costs, limits, and identity details remain
  `Unknown` until exact-boundary evidence exists.
