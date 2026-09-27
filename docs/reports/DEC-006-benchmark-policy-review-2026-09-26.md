# DEC-006 benchmark policy review

Date: 2026-09-26
Decision: accepted; evaluation remains blocked

## Outcome

DEC-006 is complete as a product-policy decision. The owner selected the
allowed source classes and conjunctive acceptance gates. No benchmark corpus,
reviewer identity, provider access, spending authority, model call, or result is
claimed by this review.

The review corrected the machine-readable v3 noninferiority margin from the
older three-point draft to the approved five-point margin. The statistical
implementation already accepts an explicit governance margin, so this is a
policy-data correction rather than an algorithm change.

## Boundary reconciliation

Exact public repositories and commits cannot be honestly frozen before the
owner-selected offline build-completion gate: the cases must represent the
completed build and remain held out from candidates. The sealed 100-case
manifest and actual independent curator/reviewer identities likewise belong to
run preregistration. They are now explicit EVAL-010 completion evidence.

This separation closes the decision without weakening readiness. The v3 record
stays `blocked`; its manifest hash, people, billing snapshot, access probe, and
owner run approval remain null. The runner must continue to fail closed.

## Review checks

- Approved thresholds agree across DEC-006, the tracker, current governance
  documentation, and `v3-governance.json`.
- The five-point margin is passed as data to the reviewed paired-statistics
  implementation; no formula or historical test vector was rewritten.
- EVAL-010 now owns exact source revisions, sealed cases, role assignments,
  protocol freeze, and trust-chain review.
- DEC-004 remains on hold. This change makes no provider calls and grants no
  credential, spend, production, or evaluation-run authority.

## Decision

Accept DEC-006 as `DONE`. Keep EVAL-010 on `HOLD` and v3 governance blocked
until the offline build-completion trigger and every preregistration field are
satisfied.
