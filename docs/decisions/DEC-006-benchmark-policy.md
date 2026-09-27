# DEC-006 — Benchmark corpus and acceptance policy

Date: 2026-09-26  
Status: accepted

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

## Deferred execution evidence

DEC-006 closes the product-policy decision; it does not authorize a benchmark
run. After the offline build-completion gate, EVAL-010 must select and freeze
the exact public repository identities and commit hashes, seal the synthetic
task manifest, and record the actual independent curator and reviewer. These
are run-specific preregistration and execution artifacts rather than policy
choices. Until they exist and every readiness field passes, v3 governance
remains blocked and no evaluation run is authorized.

The accepted five-point paired noninferiority margin supersedes the earlier
three-point v3 draft. `evals/model_allocation/v3-governance.json` is the
machine-readable current policy.
