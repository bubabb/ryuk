# DEC-006 — Benchmark corpus and acceptance policy

Date: 2026-09-26  
Status: policy approved; corpus manifest pending review

## Approved benchmark scope

The initial full evaluation will use public, version-pinned repositories and
synthetic Ryuk tasks. It will not use customer prompts, private repositories,
production records or confidential incidents.

The corpus must contain at least 100 held-out matched cases. Cases must be
sealed before candidate execution and evaluated under the existing independent,
blinded review contracts. The owner retains final acceptance authority.

## Approved acceptance gates

- At least 87% task success.
- Zero critical failures.
- The candidate's paired quality result may be no more than five percentage
  points below the baseline under the preregistered noninferiority analysis.
- A savings claim requires at least 25% measured all-in cost reduction.
- Missing usage, billing, failed-attempt or review cost prevents a savings claim.

All gates are conjunctive. Passing an aggregate rate cannot override a critical
failure, incomplete evidence or a failed paired-quality bound.

## Remaining completion evidence

DEC-006 remains in `REVIEW` until the deferred curation step records the exact
public repository identities and commit hashes, the sealed synthetic task
manifest, and the named independent review owner(s). EVAL-010 remains deferred
until the offline build-completion gate and must produce that evidence before
any evaluation run is authorized.
