# Ryuk execution plan through September 30, 2026

Date prepared: 2026-09-28
Milestone: bounded live-test entry or evidence-backed no-go by 2026-09-30

## Commitment boundary

September 30 is two calendar days after this plan was prepared. Completing all
22 open items by then is neither feasible nor truthful: seven Phase 2B items
depend on external NVIDIA/account evidence, while several held items span later
implementation, evaluation and production-certification phases.

The deadline commitment is therefore:

1. obtain and review the missing provider/account evidence;
2. run only prerequisite-compliant bounded live checks;
3. begin live testing if every entry gate passes, otherwise publish a precise
   no-go without weakening the gates; and
4. leave the repository tested, reviewed, documented and resumable.

Passing this milestone permits controlled synthetic/public live testing. It is
not Phase 2B completion, production activation or rollout approval.

## Corrected dependency chain

```text
Human/provider evidence
  -> P2B-002
  -> P2B-003, P2B-004, P2B-005
  -> CTX-003, WF-012, WF-013
  -> CTX-004 / Phase 4 exit
  -> TOOL-001 / Phase 5 exit
  -> MEM-001 / Phase 7 memory exit (Phase 6 collaboration is optional)
  -> CACHE-001 / Phase 9 cache exit (Phase 8 specialists are optional)
  -> offline build-completion gate
  -> EVAL-010
  -> P2B-006 and P2B-007
  -> P2B-008 owner decision
  -> SEC-001 and PROD-001 certification work
```

`COLLAB-001`, `SPEC-001`, `CP-005`, `CP-006`, and `CP-007` remain
post-initial-release work under DEC-008. They do not block a bounded initial
live test.

## Workstreams and delegation

| Order | Items | Unblock condition | Primary | Support/review | September 30 outcome |
| ---: | --- | --- | --- | --- | --- |
| 1 | P2B-002 | Authenticated NVIDIA dashboard/recent-request or provider-support evidence for exact account/route mapping, Kimi entitlement, readiness, queue and async disposition | Human operator obtains evidence; Sol/high analyzes it | Luna/medium sanitizes and indexes; Astra/high reviews against DEC-007 | Conditional close or explicit no-go |
| 2 | P2B-003 | P2B-002 plus a new diagnostic hypothesis; never repeat failed calls merely to seek a different result | Sol/medium | Luna/medium summarizes measurements | At most one newly justified bounded check |
| 3 | P2B-004 | Non-disruptive provider contract/evidence or naturally observed failure | Sol/high | Luna/medium tabulates; Astra/high reviews cancellation and unknown-outcome semantics | Close only evidenced cases; never induce overload |
| 4 | P2B-005 | Stable ordinary generation and model-specific structured/tool contract evidence | Sol/high | Luna/medium prepares fixtures; Astra/high only for authority/core semantics | Conditional bounded contract checks |
| 5 | CTX-003 | Verified identity, tokenizer/template, capacity and structured/tool overhead evidence | Sol/high | Luna/medium collates sources; Astra/high reviews count-to-execution and fallback binding | Begin only if provider gates land early |
| 6 | WF-012 | P2B-001 through P2B-004 and real cancellation/late-result evidence | Astra/high contract, then Sol/high implementation | Luna/medium observation tables | Remains held if provider evidence is absent |
| 7 | WF-013 | Verified usage/billing telemetry and explicit unknown-usage policy | Sol/high | Luna/medium collates terms; Astra/high reviews budget semantics; human owns spend policy | Fail-closed design may progress; closure is evidence-dependent |
| 8 | CTX-004 | CTX-003 plus approved retention scope | Astra/high design, Sol/high implementation | Luna/medium labeled fixtures | Unlikely by deadline |
| 9 | TOOL-001 | Phase 4 exit and owner-approved tool policy | Astra/high threat model, Sol/high implementation | Luna/medium command inventory and docs | After the deadline unless earlier gates finish |
| 10 | MEM-001 | Phase 5/tool exit plus owner-approved retention/sharing/deletion rules | Astra/high design, Sol/high implementation | Luna/medium synthetic fixtures | Initial-release requirement; not blocked by COLLAB-001 |
| 11 | CACHE-001 | Memory exit plus stable accepted-result, provenance and invalidation policy | Sol/high | Luna/medium cases; Astra/high tenant/provenance review | Initial-release requirement; not blocked by SPEC-001 |
| 12 | EVAL-010 | Offline build-completion gate, exact repositories/revisions, sealed 100-case corpus, named independent curator/reviewer | Astra/high audit, Sol/high deterministic fixes | Luna/medium evidence index; humans fill independent roles | Do not execute early |
| 13 | P2B-006 | P2B-002 through P2B-004 | Sol/high | Luna/medium report; Astra/high duplicate/provenance review | One controlled failover only if all gates pass |
| 14 | P2B-007 | DEC-006, P2B-003 and EVAL-010 | Sol/high | Luna/medium reporting; Astra/high methodology review; owner evaluates thresholds | Not credible by deadline unless corpus and roles already exist |
| 15 | P2B-008 | P2B-002 through P2B-007 | Astra/high | Luna/medium evidence index; owner signs decision | Owner decision only after complete evidence |
| 16 | SEC-001, PROD-001 | Approved production design and all applicable build/evaluation/provider gates | Sol/high harnesses and runbooks | Astra/high security/final evidence review; human drills and rollout approval | Not a September 30 live-smoke prerequisite |
| 17 | COLLAB-001, SPEC-001, CP-005, CP-006, CP-007 | Post-release triggers in DEC-008 | Sol/high implementation with Astra/high design/review where recorded | Luna/medium fixtures and evidence formatting | Remain deliberately held |

Luna never makes architecture, security, certification or activation decisions.
Sol is the default implementer. Astra is reserved for identity, security,
concurrency, unknown-outcome, methodology and final evidence review. Humans own
credentials, provider/account access, spending, independent-review roles and
activation decisions.

## Minimum live-test entry gate

Every applicable condition must pass on the exact tested revision:

- configured model ID agrees with authenticated account/catalog mapping and the
  live response identity;
- each candidate in scope has a stable small ordinary-generation point;
- immutable profile and adapter contracts reject unknown capabilities;
- only synthetic/public inputs are used;
- credentials remain environment-injected and absent from logs/artifacts;
- free entitlement and the USD 0 paid-spend ceiling are confirmed;
- timeout, token, attempt and concurrency bounds are preregistered;
- unknown outcomes receive no automatic retry, failover or replay;
- HTTP 202 handling fails closed unless a durable reconciliation design is
  separately approved;
- the smoke manifest and deterministic acceptance checks are fixed before the
  run;
- stop conditions and the disable/rollback action are named;
- offline tests, lint, typing, compilation and credential scans pass; and
- the owner records an explicit go/no-go.

If Kimi remains unavailable, a DeepSeek-only diagnostic may run only when
explicitly scoped as such. It is not a Phase 2 exit, cross-deployment failover or
two-profile certification.

## September 29 schedule

### Morning

- Human: obtain the authenticated dashboard/recent-request record or open a
  provider-support case; confirm free entitlement and preserve no secrets.
- Luna/medium: format the sanitizer checklist and evidence index.
- Sol/high: dry-run the bounded smoke manifest and evidence ingestion offline.
- Astra/high: review identity, stop, unknown-outcome and no-retry gates.

### Afternoon decision gate

- If Kimi entitlement/readiness and request disposition are explained, approve
  at most one bounded diagnostic tied to the new hypothesis.
- If evidence is absent, stop Kimi work. Choose DeepSeek-only diagnostics or a
  no-go; do not start P2B-006 or P2B-007.
- Process any non-disruptive P2B-004/P2B-005 provider evidence in parallel.

The offline live-test manifest validator is implemented at
`scripts/validate_phase2b_live_test_manifest.py`. It does not authorize a call;
the human reviewer must inspect the referenced account evidence, hypothesis and
approval before execution.

## September 30 schedule

### Morning

- Run only prerequisite-compliant bounded live smoke checks.
- Sanitize and review evidence immediately after each run.
- Run one controlled P2B-006 failover only if P2B-002 through P2B-004 genuinely
  pass first.

### Afternoon

- Do not start the 100-case P2B-007 benchmark unless EVAL-010 is genuinely done
  and both profiles are stable.
- Record the owner go/no-go. The likely truthful result is either “bounded live
  diagnostics started” or “blocked pending provider evidence,” not full Phase
  2B certification.
- Update tracker and handoff, run the complete verification suite, review the
  diff, commit and push.

## Stop conditions

Stop immediately on payment/subscription/provisioning prompts, ambiguous
pricing, exhausted free entitlement, identity mismatch, private/customer data,
missing sanitized evidence, repeated unknown outcomes, or a failed offline
gate. A deadline does not waive these conditions.
