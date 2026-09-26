# V3 readiness-bundle preflight packet

Status: contract template only. No real receipt, identity, approval, billing
evidence, access probe, case, response, usage, or model call is included.

## Pre-run bundle

Place all referenced artifacts beneath one bundle directory and use relative,
non-escaping paths. A pre-run bundle contains ready governance, the sealed
curation manifest, its exact compiled execution manifest, an applicable billing
snapshot, a successful assignment-complete access probe, and explicit owner
approval. The run/review/savings paths must be null.

The owner approval binds the resolved manifest SHA-256, the frozen governance
policy SHA-256, access-probe ID, billing-snapshot ID, exactly 200 calls, and the
synthetic/public-only restriction. The runner requires this validated pre-run
bundle in addition to governance; populated strings alone cannot authorize v3.

The compiled v3 manifest permits no infrastructure retry. The 200-call approval
is therefore an attempt ceiling, not just a planned-task count. An interrupted
run remains incomplete and cannot be resumed under the same approval.

```text
python scripts/model_allocation_preflight.py path/to/bundle.json \
  --manifest path/to/execution-manifest.json \
  --output path/to/preflight-report.json
```

## Post-run bundle

After execution, copy the pre-run descriptor, set `phase` to `post_run`, and add
the run directory, finalized blinded-review ledger, and savings-evidence ledger.
Post-run validation also requires every planned response and complete candidate
measurement, binds the reviewer to governance, and requires the embedded billing
snapshot to equal the pre-run snapshot exactly.

The generated report says only that the supplied records are internally
consistent. `external_evidence_claimed_not_proven` remains true: this validator
cannot establish that a human identity, authorization, provider observation, or
billing source is genuine.

## Required schemas

- `v3-readiness-bundle.schema.json`
- `v3-access-probe.schema.json`
- `v3-owner-approval.schema.json`
- `v3-case-manifest.schema.json`
- `v3-review-ledger.schema.json`
- `v3-savings-evidence.schema.json`

The standalone billing snapshot must exactly match the `billing_snapshot`
object defined by `v3-savings-evidence.schema.json`.
