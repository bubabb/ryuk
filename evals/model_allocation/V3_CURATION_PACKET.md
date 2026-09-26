# V3 held-out case curation packet

Status: template only. No cases, identities, approval, or model calls are
recorded by this packet.

## Roles and sequencing

1. The owner identifies the candidate authors and an independent curator.
2. Before candidate access, the curator freezes the sampling frame, records its
   SHA-256, selects exactly the preregistered stratum counts, and authors the
   sealed curation manifest against `v3-case-manifest.schema.json`.
3. The curator checks that every input is synthetic or public, records a stable
   reference and content hash, and confirms it is absent from v1/v2, candidate
   examples, and candidate-author access.
4. The curator defines exactly one hidden grading mode per case: exact expected
   JSON, executable checks, or independent-review criteria. Grading material
   must never be copied into the candidate prompt.
5. The curator freezes the allocation model and effort per case. The compiler
   always assigns the matched baseline to `gpt-6-astra/high`.
6. Run the offline validator and compiler; independently inspect the resulting
   200 tasks for identical paired semantics. Do not commit a manifest containing
   confidential or customer data.
7. Record the resolved execution-manifest hash and curator identity in
   `v3-governance.json` only after review. A distinct reviewer, billing snapshot,
   model-access probe, and explicit owner approval are still required before
   `--run`.

## Required distribution

| Stratum | Cases |
| --- | ---: |
| bounded evidence and documentation | 15 |
| scoped implementation | 35 |
| security and tenant boundaries | 15 |
| concurrency and recovery | 15 |
| architecture and evaluation | 20 |

Total: 100 cases and, after deterministic expansion, 200 matched calls.

## Offline commands

Validation only:

```text
python scripts/model_allocation_curation.py path/to/sealed-curation.json
```

Inspection only (prints the compiled manifest; it does not write or call a
model):

```text
python scripts/model_allocation_curation.py \
  path/to/sealed-curation.json --compile
```

## Review checklist

- [ ] Curator differs from every candidate author; reviewer is separately named.
- [ ] Sampling frame was frozen before selection and its digest is retained.
- [ ] Exactly 100 unique cases match the five preregistered counts.
- [ ] Every source is synthetic/public and content-addressed.
- [ ] All three holdout attestations are supportable for every case.
- [ ] Prompts contain no expected answers, checks, rubrics, or reviewer feedback.
- [ ] Exactly one grading mode is complete and independently usable per case.
- [ ] Critical flags cover every applicable governance hard stop.
- [ ] Allocation assignments were frozen before any candidate response.
- [ ] Compiled pairs differ only in id, arm, model, and effort.
- [ ] Resolved manifest hash matches governance before any run approval.
- [ ] Billing, access-probe, reviewer, and owner-approval evidence is complete.

Declarations are audit records, not proof by themselves. If any item cannot be
supported, leave governance blocked.
