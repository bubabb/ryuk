# Phase 2A identity and history review

Date: 2026-09-15. Baseline commit: `4e994c0`.
This report supersedes the initial 232-test offline-failover review.

## Readiness decision

The implemented offline identity/history slice passes validation. The owner
approved offline-first implementation, synthetic/public inputs only, no private
repositories, and catalog identity as observed on 2026-09-15. P2A-003/P2A-007
are closed for this offline scope. Live certification and production activation
remain pending; this is not a production readiness decision.

## Implemented and reviewed

- P2A-006: 16 bidirectional fixture-driven cross-model failure tests. Overload,
  adapter timeout, malformed choices, and response-size failures retain ordered
  attempts. A required model excludes the other model from fallback.
- P2A-008: immutable configured deployment/model snapshots on all router
  attempts, versioned JSON serialization/replay, legacy v1 compatibility, and
  API terminal persistence for both successful and failed inference. Snapshot
  history survives SQLite close/reopen and registry replacement under the same
  deployment IDs. Successful terminal records also retain final provenance.
- P2A-003 technical work: hosted catalog evidence is OBSERVED rather than
  VERIFIED; required but missing revision evidence remains CONFIGURED_ONLY.
  Missing response model identifiers fail as protocol errors; mismatches fail
  as identity errors. Catalog-only evidence cannot pass production startup.
  Owner acceptance for live hosted activation is still pending, as documented in
  ADR-010 and the product decision proposal.

The configured DeepSeek profile revision `0731` is retained in attempt
snapshots; it is not invented as an observed artifact revision. Failed
attempts do not claim that generation occurred. Adapter timeout failover is
only exercised while global deadline budget remains.

## Additional independent control-plane work

- CP-002/CP-003: ADR-009 defines commit-before-success, sanitized 503 on failed
  commit after successful inference, preservation of original failures, and
  no automatic replay after uncertain commits. Tests cover capacity release,
  duplicate correlation IDs, and commit followed by lost acknowledgement.
- CP-004: event attributes use a scalar operational field allowlist. Unknown
  fields and nested containers are excluded; tests cover alternate secret
  keys, prompt/output/auth fields, arbitrary objects, control characters, and
  invalid counts.

The API terminal policy is now `api-control-v2`. Attempt fields are additive;
legacy records remain readable. No database schema migration was introduced.
Clients parsing identity status must accept the new `observed` value; clients
parsing attempts must tolerate schema_version and configured_deployment.

## Validation and review evidence

| Check | Result |
| --- | --- |
| Full pytest suite | 256 passed, 8 skipped, 7.53 seconds |
| Ruff: backend, tests, scripts | Passed |
| Mypy: backend, tests, scripts | Passed, 80 source files |
| Compileall: backend, tests, scripts | Passed |
| Routing evaluation | Accepted; no acceptance failures |
| Audit mechanics evaluation | Accepted; four synthetic cases |
| Diff whitespace and changed-file review | Passed |

Review covered both success/failure attempt construction, history serialization,
API terminal paths, uncertain record commits, catalog evidence classification,
production startup rejection, safe events, and compatibility with existing
contracts. The initial review found catalog verification overstatement and
missing response-model validation; both were corrected and regression-tested.
No unresolved blocking finding was found in this implemented slice. This is
not a claim that all roadmap work or production certification is complete.

The sandboxed API tests hung and were interrupted; the full suite completed
using the approved pytest execution path. Eight opt-in contracts were skipped:
PostgreSQL, two Redis contracts, Dynamo, self-hosted NIM, hosted NVIDIA,
SGLang, and vLLM. No credentials, external traffic, or live-service evidence
were used to close these items.

## Remaining scope

Offline scope and identity constraints have been approved. Live product decisions
remain pending (including DEC-007 for activation identity). See
`product-decisions-proposal-2026-09-15.md` for concrete proposed choices and
missing access/budget information. Phase 2B's eight live certification items
remain blocked. Offline workflow implementation may now proceed;
context, tools, collaboration, memory, modalities, caching, and production
certification remain behind their recorded phase dependencies.

Distributed store/admission failover, process-crash reconciliation, Vault
lifecycle, backup/restore, and production performance/security drills still
need their intended infrastructure and operational evidence. Local passing
tests do not satisfy those gates. The action tracker retains these items open.
