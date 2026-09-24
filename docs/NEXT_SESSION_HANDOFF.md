# Ryuk next-session handoff

Date: 2026-09-24
Repository: `/home/sudosu/projects/ryuk`

## Resume objective

**WF-008 is complete. Next: WF-009, the offline Phase 3 exit review.** Compare
implemented evidence with the broader phase plan before advancing to CTX-001.
Live certification remains pending.

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

WF-009 should explicitly reconcile the offline milestone with the phase plan's
broader scheduler, startup recovery, external cancellation and cost/task-budget
requirements. Add stable follow-up IDs for implementation gaps or recorded
scope deferrals. Do not equate WF-008 completion with full production Phase 3
certification or silently unlock context/tool/memory phases.

No automatic scheduler or public execution/validation/recovery route exists.
Internal execution remains explicitly invoked; deadlines start at dispatch.
Unknown provider outcomes remain uncertain and cannot auto-retry. SQLite and
creation-time quota estimates are offline references, not distributed worker
admission or a durable billing ledger. Policies check supported deterministic
rules, not factual truth. Real-input retention/security and live certification
remain pending.

## Development model allocation

Read `docs/MODEL_TASK_ALLOCATION.md` before the next task. All 26 open tracker
items have primary/support/review assignments. WF-009: GPT-6 Sol/high; use Astra
only for unresolved exit/architecture claims. Luna is for bounded evidence and
documentation tasks. This does not change Ryuk's runtime models or enable agents.
The requested 87% correctness target remains empirically unverified; the report
records the completed static review and a proposed measurable acceptance gate.
