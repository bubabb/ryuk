# Ryuk next-session handoff

Date: 2026-09-25
Repository: `/home/sudosu/projects/ryuk`

## Resume objective

**CTX-002 is complete. Next: check CTX-003's evidence gate** for verified
candidate tokenizer/template identities and Phase 2B generation contracts.
CTX-003 remains HOLD until that evidence exists; do not treat estimates or
synthetic counters as deployment evidence. ADR-017 and ADR-018 plus
`backend/context/` provide offline fitting and scoped conversation/source
libraries, but neither is wired to API dispatch. Keep synthetic/public inputs
only. The Phase 3 review accepts the offline single-task exit while
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

Read `docs/ACTION_ITEMS.md`, the Phase 4 requirements in
`RYUK_DEVELOPMENT_PHASE_PLAN.md`, ADR-017/018, `backend/context/`, and the
offline deployment profiles before considering CTX-003.

Start by reviewing the CTX-003 prerequisites in `docs/ACTION_ITEMS.md`,
`RYUK_DEVELOPMENT_PHASE_PLAN.md` and the offline deployment profiles. Any
offline-only evidence gathering must preserve unknown tokenizer/template or
capacity claims; no provider calls, artifact downloads or production activation
are authorized by this handoff. If the Phase 2B contract prerequisites remain
unmet, keep CTX-003/004 on HOLD and identify a separately approved READY task.
Do not treat the Phase 3 offline exit as production approval.

No automatic scheduler or public execution/validation/recovery route exists.
Internal execution remains explicitly invoked; deadlines start at dispatch.
Unknown provider outcomes remain uncertain and cannot auto-retry. SQLite and
creation-time quota estimates are offline references, not distributed worker
admission or a durable billing ledger. Policies check supported deterministic
rules, not factual truth. Real-input retention/security and live certification
remain pending.

## Development model allocation

Read `docs/MODEL_TASK_ALLOCATION.md` before the next task. All 31 current open
tracker items have primary/support/review assignments. CTX-003: hold pending
verified deployment evidence; Sol/high implementation and Astra/high review
only after the gate. Luna can collate bounded evidence. Luna is for bounded
evidence and documentation tasks. This does not change Ryuk's runtime models or
enable agents.
The requested 87% correctness target remains empirically unverified; the report
records the completed static review and a proposed measurable acceptance gate.

## CTX-002 conversations and source-filtered context (2026-09-25)

- ADR-018 adds `SQLiteContextStore` for tenant/project/user-scoped conversations
  and immutable source revisions. `ContextBuilder` applies server-owned policy,
  checks conversation and source permissions before loading content, and fails
  closed instead of returning partial context. CTX-001's fitting function then
  consumes the returned source-linked segments.
- Project membership comes from a trusted `ContextPrincipal`; the context
  package does not authenticate users or resolve project membership itself.
  SQLite and this builder are offline libraries, not a public API or production
  data store. Correction/deletion, retention and dispatch integration remain
  open.
- Ten preparation tests and nine conversation/source tests passed. Full suite:
  386 offline tests passed, 8 integration tests deselected; Ruff, Mypy across
  105 sources, compileall and `git diff --check` passed.
- Next: qualify CTX-003's verified-tokenizer/template and Phase 2B evidence gate;
  keep it HOLD if the evidence is unavailable. CTX-004 remains held for source
  correction, compaction and two-candidate context evaluation.

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
