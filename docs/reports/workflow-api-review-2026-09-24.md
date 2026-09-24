# WF-008 governed workflow API review

Date: 2026-09-24. Scope: synthetic/public offline inputs; no live endpoint calls.

WF-008 adds authenticated create/status/cancel/result routes, with tenant authority
from the existing API-key principal and shared role/admission/terminal-record
handling. Creation atomically binds server-owned acceptance rules and execution
budget. The internal executor and validator enforce the saved binding. ADR-016
records HTTP semantics, schema v5 migration and the opt-in configuration format.

Evidence in tests/test_workflow_api.py (29 cases), plus existing workflow suites:

- All four routes require valid credentials and inference/admin authority;
  revoked/expired keys, operator-only roles and forged tenant headers fail closed.
- Cross-tenant IDs and legacy unbound rows are hidden. Client policy/budget/tenant
  fields and invalid or oversized generation requests are rejected.
- Duplicate/concurrent creation returns one task. Changed input or bound policy
  conflicts. Lost terminal-record acknowledgement can be retried without a
  duplicate task or inference call.
- Server policy edits do not weaken existing acceptance; caller budget or policy
  overrides conflict. Bound execution and acceptance survive database reopen.
- Ready/running/awaiting work can be cancelled, late publication is fenced, and
  cancellation racing with validation commits only one decision.
- Result retrieval requires accepted validation and checks artifact integrity;
  failed/rejected/uncertain/cancelled/unvalidated output is not exposed.
- Request/concurrency/token admission rejects before workflow mutations; permits
  release on conflicts and storage failures. Records omit prompts and rule strings.
- Workflow/binding/event writes roll back together. v4-to-v5 migration failure
  rolls back the new table and schema marker; legacy work is preserved.
- Missing configuration leaves routes disabled. Production configuration rejects
  enabling this offline SQLite implementation.

Validation using `/home/sudosu/miniforge3/envs/ryuk-ai/bin/python`:

```text
-m pytest -q -m 'not integration': 359 passed, 8 deselected
-m ruff check backend tests scripts: all checks passed
-m mypy backend tests scripts: success, 95 source files
-m compileall -q backend tests scripts: passed
git diff --check: passed
```

The full offline suite ran outside the sandbox under the existing pytest approval
because API tests previously stalled inside it. No external integration test ran.
ControlPlaneFailure now allows normal exception traceback assignment; frozen
exception instances broke context-manager propagation of expected 4xx responses.
The new route tests and full existing suite cover this correction.

Completion is limited to WF-008's management API contract. Creation queues work;
there is no automatic scheduler, public execution/validation/recovery route,
provider cancellation propagation, distributed workflow store or production
certification. Text tasks and the documented deterministic policy subset are
supported. WF-009 tracks the Phase 3 exit review and remaining scope decisions
before progressing to context preparation.
