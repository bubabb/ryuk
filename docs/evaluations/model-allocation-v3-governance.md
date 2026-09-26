# Model allocation v3 governance and readiness protocol

Date: 2026-09-25  
Status: valid but blocked; no v3 case manifest or model run exists

## Objective and frozen design

Compare Ryuk's category-based development allocation with an all-Astra/high
baseline on identical held-out cases. This evaluates development assistance,
not Ryuk runtime inference or production readiness.

- 100 matched cases and two arms, for 200 planned candidate calls.
- Allocation arm: category policy frozen per case in the future manifest.
- Baseline arm: GPT-6 Astra/high for every case.
- Strata: 15 bounded evidence/documentation, 35 scoped implementation, 15
  security/tenant boundaries, 15 concurrency/recovery, and 20
  architecture/evaluation cases.
- Synthetic or public inputs only; held out and not reused from v1/v2.

The allocation arm needs at least 94/100 passes, the minimum count whose 95%
Wilson lower bound exceeds 87%. Every pair must be graded and any critical
security, tenant, replay, secret, side-effect or hash-integrity failure is a hard
stop. Matched quality must satisfy a 3-point noninferiority margin using a
preregistered Newcombe score interval for paired proportions.

A savings decision occurs only after quality passes. It requires complete
candidate plus setup/grading/review usage, applicable billing evidence, and at
least 25% lower matched cost. Missing usage or billing is never zero.

## Readiness gate

`v3-governance.json` remains blocked until it records the resolved case-manifest
SHA-256, independent curator and distinct reviewer identities, billing snapshot,
model-access probe, reviewed paired-metric implementation SHA-256, and explicit
owner run approval.

The runner refuses v3 model calls without a valid ready record and requires its
case-manifest hash to equal the resolved manifest hash. Dry-run inspection
remains possible while blocked. Declarations do not independently prove actual
identity, access or billing.

EVAL-006 implemented and tested the paired metric without model calls. EVAL-007
adds the sealed case schema, validator, deterministic two-arm compiler and
curation checklist. It contains no real cases or identities and does not fill
any remaining readiness field. Case curation, reviewer assignment, billing,
access verification and run approval remain external gates.

The future curator must use `evals/model_allocation/V3_CURATION_PACKET.md` and
`v3-case-manifest.schema.json`. `scripts/model_allocation_curation.py` enforces
the 100-case stratum distribution and expands a valid sealed record into 200
matched tasks without making model calls. The resulting resolved manifest hash,
not the template or a draft curation hash, is the value governance must bind.
