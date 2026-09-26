# Model-allocation v3 readiness preflight review

Date: 2026-09-26  
Scope: EVAL-009, offline evidence-chain validation only

## Outcome

Accepted. The unified preflight validates a future v3 evidence bundle without
creating or asserting external evidence. Current governance remains blocked and
no populated bundle exists in the repository.

Pre-run validation recompiles sealed curation and requires exact equality with
the execution manifest. It binds the manifest digest and curator to governance,
prices every manifest model with one applicable billing snapshot, requires a
successful access probe for every model/effort assignment, and validates owner
approval for the exact manifest, governance prerequisites, access probe,
billing snapshot, 200-call limit, and synthetic/public data boundary. Approval
must follow the referenced access and billing observations.

The runner now requires this validated pre-run bundle as well as the same
governance file. Populated readiness strings alone can no longer authorize v3
model calls.

The audit also removed v3 infrastructure retries. Otherwise one retry could
exceed the approved 200 calls and its archived usage would not be represented
by the final per-task measurement. An interrupted run now remains incomplete;
replacement execution requires a new run and approval.

## Post-run review

Post-run mode additionally checks the run/manifest binding, all 200 completed
usage-bearing measurements, every response artifact, the finalized blinded
review ledger, reviewer/governance identity, the savings ledger, and exact
equality between its billing snapshot and the pre-run snapshot. Tests exercise
a complete synthetic bundle and mutations across paths, assignments, policy
binding, chronology, readiness, and usage completeness.

## Limits

Artifact paths must be relative and remain inside the bundle directory. Reports
retain `external_evidence_claimed_not_proven: true`: internal consistency cannot
prove a human identity, approval, provider observation, access, or billing
source. No real receipt, case, response, usage, identity, credential, provider
call, or spend was introduced, and no reliability or savings claim is valid.

Final verification: 466 offline tests passed and 8 external integrations were
deselected. Ruff, Mypy across 120 sources, compileall, three schema JSON parses,
`git diff --check`, and the repository credential-pattern scan passed.
