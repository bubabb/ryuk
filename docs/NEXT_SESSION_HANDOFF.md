# Ryuk next-session handoff

Date: 2026-09-28
Repository: `/home/sudosu/projects/ryuk`

## Resume objective

The deadline execution and delegation plan is
`docs/SEPTEMBER_30_EXECUTION_PLAN.md`. It targets an evidence-backed bounded
live-test entry or no-go by 2026-09-30, not impossible completion of all 22 open
items. It also corrects the initial-release chain: MEM-001 follows the Phase
5/tool exit without requiring post-release COLLAB-001, and CACHE-001 follows
the Phase 7/memory exit without requiring post-release SPEC-001. P2B-007 now
explicitly requires EVAL-010.

**P2B-001 is complete.** A protected `NVIDIA_API_KEY` authenticated to NVIDIA's
shared hosted API, and `GET /v1/models` returned HTTP 200 with both exact
owner-approved model routes: `moonshotai/kimi-k3` and
`deepseek-ai/deepseek-v4.1-flash`. No generation, provisioning, subscription,
payment, or paid-resource request occurred. The credential value and sensitive
headers were not printed or stored. This is account-visible catalog evidence,
not generation certification, proof of two physical deployments, runtime or
hardware identity, or model-weight verification.

**P2B-002 through P2B-008 are blocked; do not start P2B-006 failover or P2B-007
benchmarking.** The consolidated dependency and correctness review is
`docs/reports/phase-2b-blocker-review-2026-09-28.md`. Resume only when the named
external evidence or owner-controlled prerequisites are available. A
sanitizer-first identity probe now exists with
unit coverage. Its first live invocation on 2026-09-28 was interrupted by a
controller restart before any sanitized result was captured; that unknown
outcome was not automatically replayed. After the owner explicitly requested
continuation, a fresh bounded run reconfirmed HTTP 200 catalog access and both
exact IDs, but both generation requests reached the 120-second read timeout.

The local P2B-002 intake path is ready for that missing external evidence.
`scripts/validate_nvidia_account_evidence.py` accepts only a closed, sanitized
dashboard/provider-support schema with SHA-256 account/artifact references,
both exact routes, explicit free entitlement/readiness, and a timezone-aware
timestamp. It rejects unknown fields, raw identifiers, route mismatches and
unknown readiness, and its printed summary omits the hashes. Ten focused tests,
including a CLI redaction regression, pass. A human must still obtain and
sanitize the real provider record; the validator alone does not unblock
P2B-002 or establish Kimi identity.

The exact human collection procedure is
`docs/runbooks/P2B-002-nvidia-account-evidence.md`. It covers NGC organization
and API Catalog grant verification, exact route visibility, free entitlement,
readiness, recent-request disposition, out-of-repository artifact retention,
hash-only references and stop conditions. Public NGC documentation did not
identify a supported read-only endpoint for the required mapping, so do not
probe undocumented account APIs; use the authenticated UI or provider support.

The next authorized P2B-003 run used concurrent 300-second requests with a
64-token cap. DeepSeek V4.1 Flash returned HTTP 200 in 56.956 seconds with exact
response identity, a non-empty stopped output and complete usage (38 prompt, 14
completion, 52 total tokens). Kimi K3 again timed out, this time at 300.133
seconds. P2B-002 and P2B-003 are therefore blocked: DeepSeek has one
tested safe point and live identity observation; Kimi has neither, maximum safe
limits are unknown, and DEC-007's sanitized account/dashboard mapping remains
incomplete. Do not automatically retry or increase limits. See
`docs/reports/P2B-002-hosted-identity-progress-2026-09-28.md`,
`docs/reports/P2B-003-hosted-generation-progress-2026-09-28.md`, and the two
sanitized JSON records under `evidence/phase2b/`.

A later DeepSeek-only boundary run tested a 6,212-character synthetic input and
a separate 256-token output cap. The larger input timed out at 300.464 seconds.
The longer-output request returned HTTP 200 after 278.248 seconds with exact
identity and usage, but ended at the token cap with no user-visible content.
Neither deterministic contract passed, so neither point extends the known safe
range. The probe made no Kimi call and performed no retry. See the P2B-003
report and `evidence/phase2b/p2b-003-deepseek-limits-2026-09-28.json`.

A subsequent Kimi-only diagnostic tested NVIDIA's documented
`reasoning_effort: low`, recommended temperature 1 and a larger 256-token cap.
It also timed out after 300.189 seconds without response headers, identity or
usage. This weakens the hypothesis that the hosted default `max` effort alone
caused the prior timeouts. No Kimi structured/tool follow-up was launched because
ordinary generation remains unstable. Do not make another Kimi inference call
until account/dashboard or provider evidence clarifies readiness, entitlement,
queue behavior and any asynchronous contract. See
`docs/reports/P2B-003-kimi-low-reasoning-followup-2026-09-28.md` and
`evidence/phase2b/p2b-003-kimi-low-generation-2026-09-28.json`.

P2B-004 now also has a bounded live failure probe. Both intentionally malformed
requests timed out after about 30 seconds without returning an HTTP validation
response. Both streaming requests were cancelled locally at about two seconds,
before response headers. This proves only local bounding/closure: the provider
did not acknowledge cancellation, provider execution termination is unknown,
and there is no late-result observation channel. No overload was deliberately
induced. P2B-004 is blocked pending non-disruptive provider evidence; see
`docs/reports/P2B-004-hosted-failure-progress-2026-09-28.md` and
`evidence/phase2b/p2b-004-hosted-failures-2026-09-28.json`.

The subsequent non-inference Kimi contract review confirmed NVIDIA documents
HTTP 202 plus authenticated `/v1/status/{requestId}` polling. Prior Ryuk calls
never received headers/request IDs, so they cannot be polled. Ryuk now maps any
future 202 to a sanitized, non-retryable `asynchronous_result_pending` failure;
it does not store the provider ID, poll, fail over or replay. NVIDIA's current
Build partial-outage notice concerns SMS verification in China while Cloud
Functions is operational, so it does not explain the timeouts. The browser
control surface was unavailable, leaving DEC-007's account/dashboard mapping
open. See `docs/reports/P2B-004-kimi-async-contract-review-2026-09-28.md`.

P2B-005 now has a bounded structured-output/tool matrix. DeepSeek V4.1 Flash
returned one exact, schema-valid `lookup_status` tool proposal with exact model
identity and usage; the probe did not execute it. DeepSeek structured output
returned HTTP 200 with no content and therefore remains unverified. Both Kimi
cases timed out at 180 seconds. P2B-005 is blocked pending stable ordinary
generation and model-specific contract evidence, and the deployment
registry remains unchanged. See
`docs/reports/P2B-005-hosted-structured-tools-progress-2026-09-28.md` and
`evidence/phase2b/p2b-005-hosted-structured-tools-2026-09-28.json`.

A DeepSeek-only structured follow-up omitted the ambiguous `response_format`
field and used prompt-constrained exact JSON plus deterministic validation. It
returned HTTP 200 in 152.004 seconds with exact identity, the exact 18-character
JSON object and complete usage (41 prompt, 20 completion, 61 total). Reasoning
was present but not retained. This verifies a prompt-constrained JSON fallback,
not provider-enforced structured output. See
`evidence/phase2b/p2b-005-deepseek-prompt-json-2026-09-28.json`.

This is the highest-leverage sequence because it supplies the real-provider
identity, generation, limits, cancellation, usage, structured-output, and tool
evidence needed to unblock CTX-003, WF-012, and WF-013. Use synthetic/public
inputs only and retain DEC-004's USD 0 ceiling. Stop on payment, subscription,
paid provisioning, exhausted credits, missing free entitlement, or ambiguous
pricing. Do not start P2B-006 failover or P2B-007 benchmarking before their
recorded prerequisites pass.

The offline controller, governed single-task and graph workflows, Phase 2A
fixtures, and evaluation-governance groundwork remain implemented. EVAL-010
remains deferred until the owner-selected offline build-completion gate.
CTX-003/004 remain held until provider contract evidence exists. DEC-008 keeps
collaboration, specialist modalities, and HA after the initial release. The
intended initial release still includes governed tools, scoped persistent
memory, and provenance-preserving application caching. Their tracker status is
a sequencing `HOLD` until the recorded prerequisite phase exits, not a
post-release deferral; TOOL-001, MEM-001 and CACHE-001 remain required before
initial certification.

## User-approved scope and current activation boundary

- The intended product supports all data classifications, including private,
  customer, confidential and regulated data.
- Current offline development and provider checks remain synthetic/public-only.
- No private repositories or private/customer data may be used until DEC-003's
  approved governance controls are implemented and the applicable evidence is
  verified.
- Hosted catalog identity is observed, not artifact-verified.
- Controlled NVIDIA Developer Program endpoint discovery and Phase 2B checks are
  authorized with synthetic/public inputs. This does not authorize production
  activation or paid provisioning.
- Current paid-spend ceiling is USD 0. Stop on exhausted credits, missing free
  entitlement, payment/subscription requests, or ambiguous pricing. Any paid
  expansion requires a separate explicit owner decision.

## Current checkpoint

Prior uncommitted Phase 2A and WF-001 through WF-007 work is preserved, plus
WF-008. The owner requested a local Git checkpoint of all completed work and the model
allocation plan; consult Git history for the saved checkpoint.

- Four `/v1/workflows` management routes: create, status, cancel, accepted result.
  Existing API keys, inference/admin roles, tenant checks, quotas and sanitized
  terminal records apply. Creation queues work and never calls inference.
- `workflow_policy_config_path` maps server tenants to versioned acceptance rules
  and execution budgets; `workflow_store_path` selects the offline SQLite DB.
  Both must be set together; default is disabled; production rejects enablement.
  No local deployment configuration was activated.
- Creation atomically binds a detached policy/budget. Idempotency includes this
  binding; configuration changes make old create retries conflict, without
  changing already-created work. Status/result access uses the saved definition.
- Bound WorkflowExecutor calls omit the budget argument; overrides are rejected.
  `store.validate(tenant, workflow_id)` uses the saved rules; different explicit
  policy is rejected. Unbound offline fixtures retain their old interfaces.
- Result APIs return only accepted artifacts with matching validation. Foreign
  tenants and legacy unbound workflows receive 404. Cancellation fences late
  results but does not promise provider cancellation.
- Schema v5 adds workflow_bindings transactionally, without inventing authority
  for existing workflows. Follow ADR-016's stop-writers/backup/restore procedure.
- Schema v6 adds graph, node and event tables transactionally without inventing
  graphs for existing workflows.
- Schema v7 adds fenced graph-node execution, immutable result artifacts and a
  durable aggregate graph budget without inventing authority for old graphs.
- Schema v8 atomically hash-binds the full detached server policy to governed
  graph creation; dispatch uses the saved acceptance policy rather than mutable
  current configuration. Graph dispatch remains explicitly started and local;
  startup recovery marks expired nodes uncertain without replay.
- ControlPlaneFailure is no longer frozen, allowing normal traceback propagation
  through context managers rather than failing on intended HTTP errors.

## Verification

Using `/home/sudosu/miniforge3/envs/ryuk-ai/bin/python`:

```text
-m pytest -q -m 'not integration' with NVIDIA_API_KEY removed from the test process: 550 passed, 8 deselected
-m pytest -q tests/test_nvidia_account_evidence.py: 10 passed
-m pytest -q tests/test_nvidia_hosted_limits_probe.py: 5 passed
-m pytest -q focused hosted adapter/profile suite: 32 passed, 2 deselected
-m mypy backend tests scripts: success, 141 source files
-m ruff check backend tests scripts: all checks passed
-m compileall -q backend tests scripts: passed
changed deployment/fixture JSON parses: passed
repository NVIDIA credential-pattern scan: passed
git diff --check: passed
```

Offline pytest ran outside the sandbox under approval because sandboxed API
tests stalled. The first in-process run inherited `NVIDIA_API_KEY`; five
production configuration tests correctly rejected a direct production
credential. The passing run explicitly removed the variable from only the test
process. No general live Ryuk integration suite or GPU certification ran. The
separately bounded P2B-002 through P2B-004 probes and their incomplete results
are described above; they do not establish production activation.

## Next actions and limits

1. Investigate Kimi's repeated 120-second and 300-second read timeouts without
   another inference call. The documented low-reasoning/temperature-1 setting
   has now also failed. Use the account dashboard or provider support/status
   evidence to confirm entitlement, readiness, queue behavior and any async
   polling contract; preserve the USD 0 ceiling.
   The public documentation and service-status review is complete; the next
   evidence must come from an authenticated dashboard/recent-request view or
   provider support, not another generation request.
2. Complete DEC-007's sanitized account/dashboard mapping. Fail closed on any
   configured, catalog or response-model mismatch and keep the identity claim
   provider-attested rather than artifact-verified.
3. Extend P2B-003 limits only after ordinary generation is stable. Treat the
   DeepSeek 41-character/64-token-cap result as a tested lower bound, not a
   maximum context or output limit. Do not repeat the failed 6,212-character or
   256-token-cap boundary points without a new diagnostic hypothesis.
4. Complete P2B-004 only from non-disruptive provider evidence: determine
   whether a documented cancellation acknowledgment/late-result contract or a
   naturally observed 429/503 exists. Do not generate artificial provider load.
   A real malformed response is still unobserved; malformed requests merely
   timed out. The documented 202 path now fails closed but has not been observed
   live; do not add automatic polling without durable reconciliation design.
5. Continue P2B-005 without repeating the completed DeepSeek tool-proposal case
   or launching Kimi advanced-capability calls before ordinary generation works.
   The prompt-constrained DeepSeek JSON fallback now passes, but the earlier
   HTTP-200/no-content `response_format` result remains unverified. Do not enable
   a provider-enforced structured-output capability. Tool execution,
   continuation and authority remain out of scope.
6. Reassess CTX-003, WF-012 and WF-013 after the relevant evidence lands.
   Do not infer tokenizer, billing, cancellation, structured-output, or tool
   support from catalog visibility.

P2B-006 through P2B-008 remain blocked by their recorded dependencies. Do not
treat catalog access, a successful generation, or the Phase 3 offline exit as
production approval.

No automatic scheduler or public execution/validation/recovery route exists.
Internal execution remains explicitly invoked; deadlines start at dispatch.
Unknown provider outcomes remain uncertain and cannot auto-retry. SQLite and
creation-time quota estimates are offline references, not distributed worker
admission or a durable billing ledger. Policies check supported deterministic
rules, not factual truth. Real-input retention/security and live certification
remain pending.

## Development model allocation

Read `docs/MODEL_TASK_ALLOCATION.md` before the next task. The 22 current open
tracker items have primary/support/review assignments. CTX-003: hold pending
verified deployment evidence; Sol/high implementation and Astra/high review
only after the gate. Luna can collate bounded evidence. Luna is for bounded
evidence and documentation tasks. This does not change Ryuk's runtime models or
enable agents.
The requested 87% correctness target remains empirically unverified; the report
records the completed static review and a proposed measurable acceptance gate.

## CTX-002 conversations and source-filtered context (2026-09-25)

- ADR-018 adds `SQLiteContextStore` for tenant/project/user-scoped conversations
  and immutable source revisions. `ContextBuilder` applies server-owned policy,
  checks conversation and source permissions before loading content, and fails
  closed instead of returning partial context. CTX-001's fitting function then
  consumes the returned source-linked segments.
- Project membership comes from a trusted `ContextPrincipal`; the context
  package does not authenticate users or resolve project membership itself.
  SQLite and this builder are offline libraries, not a public API or production
  data store. Correction/deletion, retention and dispatch integration remain
  open.
- Ten preparation tests and nine conversation/source tests passed. Full suite:
  386 offline tests passed, 8 integration tests deselected; Ruff, Mypy across
  105 sources, compileall and `git diff --check` passed.
- Next: qualify CTX-003's verified-tokenizer/template and Phase 2B evidence gate;
  keep it HOLD if the evidence is unavailable. CTX-004 remains held for source
  correction, compaction and two-candidate context evaluation.

## WF-009 Phase 3 exit review (2026-09-25)

- Offline single-task exit criterion met by restart, dispatch-journal,
  reconciliation, fencing, validation-replay and API tests. This is not a
  production or distributed durability claim.
- Background dispatch and startup recovery remain absent; calls are explicit
  internal operations. Cancellation fences Ryuk state but does not stop or
  confirm provider execution. Budgets do not yet enforce durable input-token or
  monetary cost ceilings.
- WF-010–WF-014 track bounded dispatch, startup recovery, provider cancellation,
  usage/cost accounting and a future dependency graph. CTX-001 now closes one
  offline preparation slice; Phase 2B and production gates stay closed.
- Review: `docs/reports/phase-3-exit-review-2026-09-25.md`.
- Verification: 367 offline tests passed, 8 external integrations deselected;
  Ruff, targeted Mypy and `git diff --check` passed.

## Pilot v1 results (2026-09-25)

- 26 planned tasks; 23 passed, 1 critical failure (Sol migration cardinality),
  1 invalid task (Luna field type ambiguous), and 1 Astra infrastructure error.
- 23/24 valid, gradeable responses passed (95.83%); Wilson 95% interval
  79.76–99.26%. The pilot gate fails due to the critical failure and incomplete
  sample. This does not verify the 87% target.
- Per model among valid, gradeable tasks: Luna 7/7, Sol 11/12, Astra 5/5.
  Samples are small and purposive; no population or cost claim is supported.
- Astra connectivity passed on a separate unscored probe. P21 remains unrun and
  was not retried. The failed request's token use is unknown.
- Successful-turn usage is in `evals/model_allocation/PROTOCOL.md`; setup and
  reviewer usage are incomplete, and billing cannot be calculated.
- Pilot scripts and tests: `scripts/evaluate_model_allocation.py`,
  `scripts/grade_model_allocation.py`, and `tests/test_model_allocation_pilot.py`.
- The P02 type, schema-version cardinality and v2 preregistration follow-up is
  completed below; v1 remains unchanged.

## Pilot v2 preregistration (2026-09-25)

- EVAL-002 is complete without model/provider calls. `pilot-v2.json` is a
  hash-bound overlay over the unchanged v1 manifest; `PROTOCOL-v2.md` records
  the corrected measurement and continuation rules.
- P02 now requires explicit integer count fields. P20 rejects missing,
  duplicate and conflicting schema-version rows without mutation.
- `--resume` is restricted to one declared infrastructure retry, preserves the
  prior measurement, and never reruns a completed quality response.
- V2 was subsequently executed and reviewed under EVAL-003. All 26 responses
  passed without a retry or critical failure. The report is
  `docs/reports/model-allocation-pilot-v2-2026-09-25.md`.
- The bounded gate passed, but the purposive corrected rerun cannot establish
  the 87% population claim; larger independently curated and matched-baseline
  evaluation remains necessary.

## EVAL-003 pilot v2 review (2026-09-25)

- The frozen manifest from commit `a251c5a` resolved to hash
  `219858bb9511fa249753fa2bbfb50937c5f62a3233843d4b7f846b346a3be188`.
- All 26 calls completed with no infrastructure continuation or tool use. Exact
  outputs, isolated hidden assertions and response-hash-bound manual criteria
  review all passed; zero critical failures were recorded.
- Candidate usage: 371,315 input, 60,544 cached input, 9,854 output and 5,351
  reasoning-output tokens. Setup and reviewer usage remain unknown; no billing
  or savings claim is supported.
- Overall Wilson 95% interval is 87.13–100%, but model strata are small and the
  sample is purposive/synthetic. `population_claim_valid` remains false.
- CTX-003 and Phase 2B remain blocked. No currently tracked implementation item
  was READY at that checkpoint; the owner subsequently authorized WF-010.

## WF-010 bounded local dispatcher (2026-09-25)

- ADR-019 adds an explicitly started, one-shot local dispatcher with a bounded
  concurrency ceiling and graceful stop: intake closes before active calls are
  drained. Construction, workflow creation and application startup do not start
  execution.
- SQLite ready listing is advisory and capped; the existing atomic tenant claim,
  owner, lease and fence remain authoritative. Successful inference still stops
  at `awaiting_validation`.
- Conflicts and unexpected failures are isolated and reported with counters plus
  at most 100 sanitized tenant/workflow/code records. Unexpected post-claim
  failure remains conservative durable state for recovery, never silent replay.
- This is offline single-controller reference behavior, not distributed
  admission or production scheduling. There is no lease renewal, forced stop,
  provider cancellation, startup activation or automatic recovery.
- Review: `docs/reports/workflow-dispatcher-review-2026-09-25.md`. Next, WF-011
  was separately authorized and completed as recorded below.

## WF-011 conservative startup recovery (2026-09-25)

- ADR-020 runs one bounded SQLite recovery transaction during lifespan, before
  runtime-state collection, only when the opt-in offline workflow store exists.
- Expired running work is fenced to `uncertain`. Valid hash/fence-bound saved
  outcomes become `awaiting_validation` or `failed`; missing/corrupt evidence
  remains uncertain and never triggers inference.
- `WORKFLOW_RECOVERY_SCAN_LIMIT` defaults to 1000. Overflow rolls back and fails
  startup. A failed lifespan clears stale in-process recovery status and closes
  initialized resources.
- `GET /v1/workflows/recovery` requires operator/admin authority, normal
  admission/terminal recording, and returns only the authenticated tenant's
  workflow IDs, states and stable reason codes. No prompt/result/provider data
  or cross-tenant count is exposed.
- Review: `docs/reports/workflow-startup-recovery-review-2026-09-25.md`. No
  provider call, dispatcher auto-start, automatic validation or replay was
  added. Remaining WF-012–WF-014 items retain their external/product gates.
- Final verification: 400 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 110 sources, compileall, `git diff --check` and
  a repository scan for pasted API-key patterns passed.

## EVAL-004 v3 evaluation harness (2026-09-25)

- Optional comparison contracts require every case exactly once in every arm
  and identical prompt/grading semantics across arms. Reports include per-arm
  results and matched pair outcomes; incomplete pairs remain explicit.
- Manifests may require a reviewer declaration distinct from all candidate
  authors. This is mechanically enforced but is not external proof of identity
  or independence.
- `--overhead` records setup/grading/review token counters. All-in totals become
  unknown when any contributor is unknown, so missing review cost is never
  treated as zero.
- Review: `docs/reports/model-allocation-v3-harness-review-2026-09-25.md`.
  No model call, v3 preregistration, reliability/savings claim or runtime routing
  change occurred.
- Final verification: 404 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 110 sources, compileall, `git diff --check` and
  the repository credential-pattern scan passed. A copied v2 run regraded 26/26
  with its original gate intact; absent overhead correctly leaves all-in usage
  incomplete.

## EVAL-005 v3 governance (2026-09-25)

- The blocked protocol specifies 100 held-out synthetic/public matched cases
  across five strata and 200 calls: category allocation versus all-Astra/high.
- Allocation needs 94/100 passes for a Wilson 95% lower bound above 87%, zero
  critical failures and all pairs graded. Its original 3-point margin was a
  draft value, superseded by DEC-006's owner-approved 5-point margin on
  2026-09-26.
- Savings requires quality first, complete candidate/overhead usage, applicable
  billing evidence and at least 25% lower matched cost. Unknowns never become
  zero.
- V3 `--run` requires ready governance bound to the resolved manifest hash;
  blocked governance still permits dry-run inspection. Curator and reviewer must
  be distinct, and readiness hashes must be lowercase SHA-256 values.
- Review: `docs/reports/model-allocation-v3-governance-review-2026-09-25.md`.
  EVAL-006 is READY to implement the paired metric offline. No model call,
  credential use, spending or runtime-routing change occurred.
- Final verification: 413 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 112 sources, compileall, `git diff --check` and
  the repository credential-pattern scan passed.

## EVAL-006 paired noninferiority metric (2026-09-25)

- `scripts/model_allocation_statistics.py` implements Newcombe method 10 for
  allocation-minus-baseline paired proportions and a strict lower-bound
  noninferiority decision.
- The grader emits the paired gate only for complete pairs and gets its
  explicit margin from ready, manifest-bound governance (currently five points
  under DEC-006). V3 grading now
  rejects absent, incomplete, or mismatched governance.
- Six published Table III examples serve as deterministic reference vectors;
  boundary and invalid-input tests fail closed.
- Governance records the reviewed implementation SHA-256. Six unrelated
  readiness fields remain absent, so v3 is still blocked and no run is
  authorized.
- Review: `docs/reports/model-allocation-paired-metric-review-2026-09-25.md`.
  No model call, credential use, spending, case authoring or runtime-routing
  change occurred.
- Final verification: 432 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 114 sources, compileall, `git diff --check` and
  the repository credential-pattern scan passed.

## EVAL-007 v3 held-out curation contract (2026-09-26)

- `v3-case-manifest.schema.json` and `V3_CURATION_PACKET.md` define a sealed,
  case-centric process with exact preregistered strata, synthetic/public source
  provenance, holdout attestations, one hidden grading mode, and frozen
  allocation assignments.
- `scripts/model_allocation_curation.py` rejects protocol drift and deterministically
  expands 100 accepted cases into 200 identical matched tasks with an
  all-Astra/high baseline. It performs no writes or model calls by default.
- Matched-arm validation now covers provenance, strata and review criteria.
  Prose-review cases no longer enter the Python-check path, and the v3 overall
  gate requires all quality conditions together.
- Review:
  `docs/reports/model-allocation-v3-curation-contract-review-2026-09-26.md`.
  No real cases, identities, private data, credentials, billing records, model
  responses, spending, provider calls, or runtime changes were introduced.
- Final verification: 444 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 116 sources, compileall, `git diff --check` and
  the repository credential-pattern scan passed.

## EVAL-008 blinded review and savings contracts (2026-09-26)

- `v3-review-ledger.schema.json` binds blind aliases, score-freeze/unblinding
  order, reviewer independence, exact task coverage, and response hashes to the
  manifest and run.
- `v3-savings-evidence.schema.json` binds applicable model rates and complete
  per-arm setup/grading/review usage to the manifest, run, review ledger, and
  governance billing snapshot.
- `scripts/model_allocation_evidence.py` validates both records and recomputes
  all-in costs. Unknown evidence never becomes zero, and savings requires the
  matched quality gate first plus at least 25% reduction.
- V3 grading requires these strict records; loose legacy overhead remains
  supported only for v1/v2. Review:
  `docs/reports/model-allocation-v3-review-savings-contract-review-2026-09-26.md`.
- No real identity, response, usage, price, billing, access, approval, model
  call, spending, or runtime change occurred.
- Final verification: 459 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 118 sources, compileall, both schema JSON
  parses, `git diff --check`, and the repository credential-pattern scan passed.

## EVAL-009 unified v3 readiness preflight (2026-09-26)

- `scripts/model_allocation_preflight.py` validates bundle-local pre-run and
  post-run evidence chains and emits a deterministic report that preserves the
  distinction between internal consistency and externally proven evidence.
- Pre-run validation cross-binds curation, the exact compiled manifest,
  governance, complete billing rates, assignment-complete access evidence, and
  owner approval after its prerequisites. The runner now requires the validated
  bundle; readiness strings alone are insufficient.
- Post-run validation adds every measurement and response, blinded review,
  reviewer identity, and savings evidence with the identical billing snapshot.
- V3 now allows one attempt per task and no in-place resume, keeping the owner
  approval at a real 200-attempt ceiling; replacement runs require new approval.
- Schemas and instructions are in `evals/model_allocation/`; review:
  `docs/reports/model-allocation-v3-readiness-preflight-review-2026-09-26.md`.
- No real evidence, identity, case, response, usage, price, credential, model
  call, spending, or runtime-routing change occurred. Governance remains
  blocked.
- Final verification: 466 offline tests passed, 8 external integrations were
  deselected; Ruff, Mypy across 120 sources, compileall, three schema JSON
  parses, `git diff --check`, and the repository credential-pattern scan passed.

## DEC-006 benchmark policy review (2026-09-26)

- DEC-006 is DONE as a policy decision: public version-pinned repositories plus
  synthetic Ryuk tasks, at least 100 held-out matched cases, 87% success, zero
  critical failures, a five-point paired noninferiority margin, and 25% all-in
  savings are the approved conjunctive gates.
- The machine-readable governance margin is now `0.05`, correcting the older
  three-point draft. The paired-statistics algorithm was not changed.
- EVAL-010 owns the exact repository commits, sealed manifest, named independent
  curator/reviewer, protocol freeze, and trust-chain review. It remains on HOLD
  until the offline build-completion gate; v3 governance remains blocked.
- Review: `docs/reports/DEC-006-benchmark-policy-review-2026-09-26.md`.
- No benchmark, model/provider call, credential use, spending, or production
  activation occurred in the DEC-006 change.

## DEC-004 Developer Program access decision (2026-09-26)

- DEC-004 is DONE. Use NVIDIA Developer Program free resources for development,
  prototyping, testing, and evaluation; the paid-spend ceiling is USD 0.
- A protected local environment variable may supply the NVIDIA credential for
  controlled Phase 2B checks. Never record its value in Git, chat, fixtures,
  arguments, logs, reports, or test output.
- Stop on payment, subscription, paid provisioning, exhausted credits, absent
  entitlement, or ambiguous pricing. Paid expansion requires a new explicit
  owner decision with a finite cap.
- P2B-001 is now complete. The protected credential authenticated and the
  shared catalog exposed both exact approved model routes without contacting a
  generation or paid resource.
- Review: `docs/reports/DEC-004-developer-program-access-review-2026-09-26.md`.

## P2B-001 authorized endpoint inventory (2026-09-26)

- DEC-009 approved exact replacement `deepseek-ai/deepseek-v4.1-flash` while
  retaining the deprecated `-0731` evidence only for historical replay.
- The approved `env:NVIDIA_API_KEY` authenticated successfully to
  `https://integrate.api.nvidia.com`; `GET /v1/models` returned HTTP 200.
- The authenticated catalog exposed both `moonshotai/kimi-k3` and
  `deepseek-ai/deepseek-v4.1-flash` to the account.
- Both are model routes on one shared hosted API origin. No claim is made that
  they are separate physical endpoints, runtimes, hardware allocations, or
  artifact-verified weights.
- No generation, provisioning, subscription, payment, or paid-resource request
  occurred. No credential value or sensitive header was recorded.
- P2B-001 is DONE. P2B-002 through P2B-008 are blocked with named unblock
  conditions in `docs/reports/phase-2b-blocker-review-2026-09-28.md`.
- Review: `docs/reports/P2B-001-authorized-endpoint-inventory-2026-09-26.md`.
