# Ryuk next-session handoff

Date: 2026-09-25
Repository: `/home/sudosu/projects/ryuk`

## Resume objective

**CTX-001 is complete. Next: CTX-002, the offline conversation/source-store
vertical slice.** ADR-017 and `backend/context/` define and implement a
candidate-specific fitting boundary, but it is not wired to dispatch and does
not persist conversations or authorize source retrieval. Keep synthetic/public
inputs only. The Phase 3 review accepts the offline single-task exit while
tracking scheduler, startup recovery, provider cancellation, usage/cost budgets
and dependency graphs as deferred follow-ups. The model-allocation pilot v1 is
saved but fails its quality gate; 87% remains unverified. Live certification
remains pending.

## User-approved scope

- Offline implementation first, synthetic/public inputs only.
- No private repositories or private/customer data.
- Hosted catalog identity is observed, not artifact-verified.
- No live provider calls, provisioning, spending or production activation.

## Current checkpoint

Prior uncommitted Phase 2A and WF-001 through WF-007 work is preserved, plus
WF-008. The owner requested a local Git checkpoint of all completed work and the model
allocation plan; consult Git history for the saved checkpoint.

- Four `/v1/workflows` management routes: create, status, cancel, accepted result.
  Existing API keys, inference/admin roles, tenant checks, quotas and sanitized
  terminal records apply. Creation queues work and never calls inference.
- `workflow_policy_config_path` maps server tenants to versioned acceptance rules
  and execution budgets; `workflow_store_path` selects the offline SQLite DB.
  Both must be set together; default is disabled; production rejects enablement.
  No local deployment configuration was activated.
- Creation atomically binds a detached policy/budget. Idempotency includes this
  binding; configuration changes make old create retries conflict, without
  changing already-created work. Status/result access uses the saved definition.
- Bound WorkflowExecutor calls omit the budget argument; overrides are rejected.
  `store.validate(tenant, workflow_id)` uses the saved rules; different explicit
  policy is rejected. Unbound offline fixtures retain their old interfaces.
- Result APIs return only accepted artifacts with matching validation. Foreign
  tenants and legacy unbound workflows receive 404. Cancellation fences late
  results but does not promise provider cancellation.
- Schema v5 adds workflow_bindings transactionally, without inventing authority
  for existing workflows. Follow ADR-016's stop-writers/backup/restore procedure.
- ControlPlaneFailure is no longer frozen, allowing normal traceback propagation
  through context managers rather than failing on intended HTTP errors.

## Verification

Using `/home/sudosu/miniforge3/envs/ryuk-ai/bin/python`:

```text
-m pytest -q -m 'not integration': 359 passed, 8 deselected
-m mypy backend tests scripts: success, 95 source files
-m ruff check backend tests scripts: all checks passed
-m compileall -q backend tests scripts: passed
git diff --check: passed
```

Offline pytest ran outside the sandbox under existing approval, due to prior
sandbox API stalls. No external tests, live services or GPU certification ran.

## Next actions and limits

Read docs/ACTION_ITEMS.md, ADR-011 through ADR-016, the workflow modules and
`docs/reports/workflow-api-review-2026-09-24.md`.

Start CTX-002 by reading the Phase 4 requirements in
`RYUK_DEVELOPMENT_PHASE_PLAN.md`, ADR-017, and the existing authorization and
workflow-store contracts. Design the source/conversation persistence boundary
before implementation; apply authorization before selecting context. Keep the
WF-010–WF-014 and CTX-003/004 deferrals visible. Do not treat the Phase 3
offline exit as production approval.

No automatic scheduler or public execution/validation/recovery route exists.
Internal execution remains explicitly invoked; deadlines start at dispatch.
Unknown provider outcomes remain uncertain and cannot auto-retry. SQLite and
creation-time quota estimates are offline references, not distributed worker
admission or a durable billing ledger. Policies check supported deterministic
rules, not factual truth. Real-input retention/security and live certification
remain pending.

## Development model allocation

Read `docs/MODEL_TASK_ALLOCATION.md` before the next task. All 32 current open
tracker items have primary/support/review assignments. CTX-002: GPT-6 Sol/high
for implementation, Luna for bounded fixture/evidence work, and Astra for
authorization or retention boundary review. Luna is for bounded evidence and
documentation tasks. This does not change Ryuk's runtime models or enable agents.
The requested 87% correctness target remains empirically unverified; the report
records the completed static review and a proposed measurable acceptance gate.

## CTX-001 candidate-specific fitting (2026-09-25)

- ADR-017, `backend/context/` and
  `docs/reports/context-preparation-review-2026-09-25.md` define source trust,
  candidate-specific token counters/templates, output reserve and safety
  margin, deterministic optional fitting/deduplication, overflow behavior and
  payload/source provenance.
- The context library is not connected to API dispatch. Durable conversation
  storage, source authorization/retrieval, compaction, retention, production
  counters and exact candidate tokenizer/template integration remain open.
- Ten focused tests cover boundaries, required overflow, fit order, duplicates,
  fallback re-preparation, estimated counts, counter mismatch and trust roles.
  Full suite: 377 offline tests passed, 8 integration tests deselected; Ruff,
  Mypy across 102 sources, compileall and `git diff --check` passed.
- Next: CTX-002, offline conversation/source storage and authorization-filtered
  context building. CTX-003/004 retain deployment-evidence and evaluation gates.

## WF-009 Phase 3 exit review (2026-09-25)

- Offline single-task exit criterion met by restart, dispatch-journal,
  reconciliation, fencing, validation-replay and API tests. This is not a
  production or distributed durability claim.
- Background dispatch and startup recovery remain absent; calls are explicit
  internal operations. Cancellation fences Ryuk state but does not stop or
  confirm provider execution. Budgets do not yet enforce durable input-token or
  monetary cost ceilings.
- WF-010–WF-014 track bounded dispatch, startup recovery, provider cancellation,
  usage/cost accounting and a future dependency graph. CTX-001 now closes one
  offline preparation slice; Phase 2B and production gates stay closed.
- Review: `docs/reports/phase-3-exit-review-2026-09-25.md`.
- Verification: 367 offline tests passed, 8 external integrations deselected;
  Ruff, targeted Mypy and `git diff --check` passed.

## Pilot v1 results (2026-09-25)

- 26 planned tasks; 23 passed, 1 critical failure (Sol migration cardinality),
  1 invalid task (Luna field type ambiguous), and 1 Astra infrastructure error.
- 23/24 valid, gradeable responses passed (95.83%); Wilson 95% interval
  79.76–99.26%. The pilot gate fails due to the critical failure and incomplete
  sample. This does not verify the 87% target.
- Per model among valid, gradeable tasks: Luna 7/7, Sol 11/12, Astra 5/5.
  Samples are small and purposive; no population or cost claim is supported.
- Astra connectivity passed on a separate unscored probe. P21 remains unrun and
  was not retried. The failed request's token use is unknown.
- Successful-turn usage is in `evals/model_allocation/PROTOCOL.md`; setup and
  reviewer usage are incomplete, and billing cannot be calculated.
- Pilot scripts and tests: `scripts/evaluate_model_allocation.py`,
  `scripts/grade_model_allocation.py`, and `tests/test_model_allocation_pilot.py`.
- Next: fix P02's output type, add a missing/duplicate schema-version-row
  migration assertion, and preregister a new version. Preserve v1 unchanged.
