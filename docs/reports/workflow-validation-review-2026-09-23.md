# WF-006 deterministic validation review

Date: 2026-09-23. Scope: synthetic/public offline fixtures only.

Inference success now stops at awaiting_validation. The existing deterministic
audit rules drive a separate accepted/rejected decision over the saved artifact.
The durable report contains the artifact checksum, policy snapshot and validator
version. State, report and event are atomic; replay is immutable and tenant-scoped.
ADR-014 records rule semantics, limits and the schema v3 migration procedure.

Evidence in tests/test_workflow_validation.py and test_workflow_executor.py:

- Inference alone never creates accepted success; accepted and rejected paths
  preserve one engine call and its artifact/provenance.
- Required sections, lower/upper lengths, policy, citations, ASCII language,
  secret patterns, missing output and supported object schemas are exercised.
- Invalid/duplicate/nonfinite JSON and unsupported policy rules fail closed.
- Wrong tenants, missing/corrupt artifacts and failed/cancelled workflows cannot
  be accepted. Rejected output cannot be completed or dispatched again.
- Identical replay, database restart and two concurrent connections yield one
  recorded decision/event. Changed policy conflicts with the original decision.
- Validator and event failures leave no partial acceptance; retry can succeed.
- v2 successes migrate to awaiting_validation while retaining artifacts;
  injected migration failure rolls back state, table and version. Existing v1
  migration and rollback contracts also pass with v3.

Validation results are recorded in PROJECT_STATUS_REPORT.md and the handoff.
No external inference calls, infrastructure changes or live certification ran.

WF-006 is complete for the offline internal boundary. WF-007 recovery and
uncertain-call reconciliation is next. WF-008 must bind authorized acceptance
criteria before exposing an API. Deterministic acceptance makes no claim about
factual correctness or model quality; SQLite remains a reference store.
