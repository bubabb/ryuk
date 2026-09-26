# EVAL-005 v3 governance review

Date: 2026-09-25  
Scope: offline protocol and fail-closed runner authorization; no model calls

## Decision

EVAL-005 is complete. The governance record is consistent and deliberately
blocked. Its strata sum to 100 cases, 200 calls match two arms, and 94 passes is
mechanically confirmed as the first count whose Wilson 95% lower bound exceeds
87%. Quality precedes savings, hard stops override aggregate scores, and
incomplete usage or billing blocks cost claims.

## Review findings

The review tested weakened held-out, billing, review, call-count and statistical
settings. It found and fixed three fail-closed gaps:

- blocked governance initially prevented harmless dry-run inspection as well as
  calls; the final runner gates only `--run`;
- a ready record initially accepted arbitrary nonblank hash labels; the final
  validator requires lowercase 64-character SHA-256 values;
- curator and reviewer could initially share one identifier; ready governance
  now requires them to differ.

Malformed boolean margins and hard-stop lists are rejected. No unresolved
correctness issue remained. The paired interval is not implemented yet, so its
implementation hash is an explicit blocker rather than assumed capability.

The record does not contain tasks, prove representative curation or reviewer
identity, verify access, snapshot billing, authorize spend, or run a model. The
87% population and 25% savings claims remain unverified.

Nine governance tests and the combined 23 governance/pilot tests passed. Full
offline suite: 413 passed and 8 external integrations deselected. Ruff passed;
Mypy passed across 112 sources; compileall, `git diff --check`, and the
repository credential-pattern scan passed.
