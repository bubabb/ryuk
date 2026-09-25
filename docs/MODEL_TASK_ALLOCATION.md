# Ryuk model allocation to reduce development usage

Date: 2026-09-24. Scope: models assisting development of Ryuk, not models routed
by Ryuk at runtime. This does not replace Kimi/DeepSeek deployment choices or
change Ryuk's vendor-independent inference architecture.

## Recommendation and evidence

Use GPT-6 Sol as the default implementation model. Use GPT-6 Luna for bounded
support work and GPT-6 Astra for ambiguous architecture and high-consequence
reviews. Do not run every task through every model. These assignments are
engineering judgments based on task complexity and failure impact, not measured
Ryuk-specific model success rates.

Official guidance describes Luna as efficient for scoped work, Sol as a general
coding/work model, and Astra as suited to demanding analysis. It recommends
comparing models on the same inputs rather than assuming a universal winner.
[Official model-selection guidance](https://developers.openai.com/api/docs/guides/model-selection),
checked 2026-09-24.

The current session exposes `gpt-6-luna`, `gpt-6-sol`, and `gpt-6-astra` as model
identifiers. Availability in another account or session must be checked there.
Legacy models are not selected merely because they are older; no measured
quality/cost advantage for them has been established for this repository.

For comparison, the published Standard, short-context API prices per million
tokens are:

| Model | Input | Output | Equal-token cost relative to Astra |
| --- | ---: | ---: | ---: |
| GPT-6 Luna | $0.10 | $0.50 | 1% |
| GPT-6 Sol | $2.00 | $10.00 | 20% |
| GPT-6 Astra | $10.00 | $50.00 | 100% |

These are API prices, not a promise about Codex subscription limits or this
session's billing. Cached inputs, long context, service tier, tool use, reasoning
and retries affect actual usage. [Official pricing](https://developers.openai.com/api/docs/pricing),
checked 2026-09-24. Recheck before making spending decisions.

Illustration only: with the same input/output proportions and total token volume,
30% Luna + 60% Sol + 10% Astra costs 0.30×0.01 + 0.60×0.20 + 0.10×1 = 22.3%
of all-Astra Standard API spend (77.7% less). This is not a forecast: shorter
prompts, extra review tokens and rework can change the result substantially.

## Allocation rules

- **Luna / low or medium:** inventory, formatting, documentation updates from
  verified evidence, extracting test results, narrowly specified fixtures.
  It must not invent evidence, decide architecture or certify security.
- **Sol / medium:** default for scoped code, adapters, tests and research briefs.
  Use high effort for boundary conditions, migrations and multi-module changes.
- **Astra / high:** difficult design, conflicting requirements, concurrency,
  security boundaries, or review of evidence with consequential unknowns.
  Use a focused review packet; do not send the entire history by default.
- **Human:** product policy, credentials/spending, environment activation and
  production acceptance. Models prepare recommendations; they do not supply
  missing authority or real-system evidence.

The table names the primary model for substantive work and the smaller support
slice where useful. A review is a separate pass; this document does not authorize
parallel agents or automatic model launches. Prefer one implementer at a time.

## All open tracker items

Statuses are preserved from ACTION_ITEMS.md. Assignment does not unblock an item.
“Review” is the minimum evidence check before closure, not approval to begin live
work. Effort levels are starting settings, not calibrated guarantees.

| ID | Status | Primary model / effort | Cheaper bounded work | Required review or decision and rationale |
| --- | --- | --- | --- | --- |
| DEC-001 | HOLD | Sol / medium | Luna summarizes approved environment options | Owner chooses hosted vs self-hosted; Sol can compare a defined shortlist without an Astra pass unless architectural constraints conflict. |
| DEC-002 | HOLD | Sol / medium | Luna extracts exact model IDs from verified sources | Owner approves models/revisions; verify current publisher/engine compatibility, never infer availability from a name. |
| DEC-003 | REVIEW | Sol / high | Luna inventories existing data flows | Owner defines classification/residency/retention/disclosure; Astra reviews conflicting data boundaries. A model cannot supply legal or organizational approval. |
| DEC-004 | HOLD | Sol / medium | Luna formats a secret-free access/budget checklist | Owner authorizes credentials, hardware and spend. Astra only for unresolved secret-boundary design; no credentials in prompts or reports. |
| DEC-006 | HOLD | Sol / high | Luna formats pinned benchmark manifests | Astra reviews leakage, representativeness and metric incentives; owner approves tasks/thresholds. Cheap corpus formatting is separate from evaluation design. |
| DEC-007 | HOLD | Astra / high | Luna organizes sanitized identity observations | Owner approves live identity policy. Opaque hosted identity and unknown evidence require careful architectural review. |
| P2B-001 | BLOCKED | Sol / medium | Luna formats endpoint inventory | Owner authorization and endpoint evidence required. Execute only approved provisioning/runbooks; model selection does not authorize spending. |
| P2B-002 | BLOCKED | Sol / high | Luna collates sanitized readiness results | Astra reviews identity claims against DEC-007; real endpoints must prove auth/readiness/served identity. |
| P2B-003 | BLOCKED | Sol / medium | Luna summarizes already-produced measurements | Deterministic harness and reproducible report suffice when contracts are fixed; escalate to Sol/high or Astra only on unexplained limits. |
| P2B-004 | BLOCKED | Sol / high | Luna tabulates failure cases | Astra reviews timeout/cancellation/late-result semantics; real failure tests are mandatory and cannot be replaced by model confidence. |
| P2B-005 | BLOCKED | Sol / high | Luna adds fixtures from an approved contract | Sol checks positive and negative structured/tool contracts; Astra only if tool authority or task semantics change. Outputting tool calls is not permission to execute them. |
| P2B-006 | BLOCKED | Sol / high | Luna summarizes per-attempt evidence | Astra reviews duplicate execution, budget continuity and provenance across real failover. |
| P2B-007 | BLOCKED | Sol / high | Luna formats harness outputs and charts from saved data | Astra reviews methodology once, not every run; deterministic scripts calculate metrics; owner evaluates approved thresholds. |
| P2B-008 | BLOCKED | Astra / high | Luna builds the evidence index | Astra synthesizes certification gaps; owner signs activation/rejection. A model cannot turn missing tests into certification. |
| WF-009 | READY | Sol / high | Luna cross-references tracker/ADR/test evidence | Astra reviews only disputed exit claims, not the whole inventory. Owner resolves scope deferrals; review must distinguish the offline milestone from the broader phase plan. |
| CP-005 | HOLD | Astra / high for lease/fence design; Sol / high for implementation | Luna documents settled invariants | Astra reviews concurrency/crash safety; fault tests must prove capacity cannot silently reopen. Whole-task Luna assignment is unsuitable. |
| CP-006 | HOLD | Sol / high | Luna formats migration/restore evidence | Astra reviews destructive migration and recovery assumptions; real restore drills establish RPO/RTO. |
| CP-007 | HOLD | Astra / high for failure model; Sol / high for harness | Luna organizes chaos-run evidence | Astra reviews partition/failover invariants; real multi-replica tests required. Reduce model use during deterministic test execution. |
| SEC-001 | HOLD | Sol / high | Luna writes sanitized runbook text from approved steps | Astra reviews workload authority and rotation/revocation boundaries; operator conducts authorized drills. |
| CTX-001 | HOLD | Astra / high for ADR; Sol / high for implementation | Luna creates explicit boundary fixtures | Astra reviews tokenizer/template provenance, reserve math and fallback preparation. Requires Phase 3 exit evidence first. |
| TOOL-001 | HOLD | Astra / high for threat model; Sol / high for implementation | Luna inventories approved commands and documents policy | Astra reviews authority/isolation/side effects; owner approves tool policy and adversarial sandbox tests must pass. |
| COLLAB-001 | HOLD | Astra / high for bounded orchestration; Sol / high for implementation | Luna collates accepted task evidence | Astra reviews retry/review budget multiplication and generator-reviewer separation; Phase 2/5 gates remain mandatory. |
| MEM-001 | HOLD | Astra / high for data/evidence/deletion design; Sol / high for implementation | Luna formats synthetic memory fixtures | Owner approves retention/sharing; Astra reviews tenant isolation, deletion propagation and source trust. |
| SPEC-001 | HOLD | Sol / high for one approved modality slice | Luna curates synthetic fixtures with explicit labels | Astra reviews only the new modality's trust/architecture boundary; real modality evaluation required. Split this broad item before implementation. |
| CACHE-001 | HOLD | Sol / high | Luna documents cache keys and invalidation cases | Astra reviews tenant/policy/provenance isolation and stale-result acceptance; deterministic invalidation tests required. |
| PROD-001 | HOLD | Sol / high for harnesses/runbooks; Astra / high for final evidence review | Luna indexes measured load/soak/restore reports | Owner approves rollout. Models cannot certify unrun chaos, restore, incident-response or production gates. Split into separately measurable gates. |

No entire open item is assigned to Luna alone: this backlog consists of policy,
certification, or architectural work. The intended Luna savings come from bounded
subtasks inside those items, plus routine documentation after verification.

## Additional status-report work not yet separately tracked

These are mappings of existing report gaps, not additional completed work or
permission to bypass dependencies. WF-009 should reconcile workflow-related scope;
new implementation slices need stable tracker IDs before starting.

| Work described in PROJECT_STATUS_REPORT.md | Suggested allocation |
| --- | --- |
| Streaming, disconnects and cancellation propagation | Sol/high implementation; Astra/high lifecycle and quota-release review |
| End-to-end structured output and tool-call output | Sol/high contracts/adapters; Astra only if authority or core semantics change |
| Multimodal, embeddings and reranking | SPEC-001: Sol/high per slice, targeted Astra trust review |
| Model-auditor calibration | Sol/high harness; Astra/high evaluation methodology and false-accept analysis; owner risk thresholds |
| Dynamo/TensorRT-LLM adoption gates | Sol/high current official research and reproducible benchmark; Astra/high architecture tradeoffs; owner adoption decision |
| Supply-chain scans, SBOMs and attestations | Sol/high enforcement; Astra/high trust/activation review; Luna organizes verified reports |
| Telemetry, SLOs, dashboards, runbooks, load/soak/chaos and disaster recovery | Sol/medium for scoped telemetry, Sol/high for harnesses, Astra for invariants/final evidence; Luna formats reports |
| Dependency compatibility, license and vulnerability gates | Sol/medium routine updates; Sol/high breaking changes; Astra only for unresolved security/architecture issues; human policy decisions |
| Live-provider lookup for uncertain outcomes | Astra/high evidence/replay contract; Sol/high approved adapter implementation; live authorization and provider evidence required |

The old Starlette/httpx warning is already closed by QA-001 and is not new work.

## Review of these assignments and the requested 87% target

I performed a second, adversarial self-review after drafting the mapping. This
is not an independent model evaluation, a statistical confidence score or a
claim that execution will be 87% correct.

Review checks for every row:

1. Matches a currently open tracker ID and preserves its blocking conditions.
2. Assigns real implementation/evidence work separately from owner authorization.
3. Does not place ambiguous architecture, security or concurrency solely with Luna.
4. Uses a cheaper model for separable routine work; avoids mandatory Astra review
   where deterministic tests and a fixed contract suffice.
5. Names the evidence or escalation needed before claiming completion.

Review findings and resulting decisions:

- The first cost-saving idea, using Luna to close the WF-009 evidence inventory,
  was too broad: exit claims need cross-module judgment. Final owner: Sol/high;
  Luna only gathers references, with Astra for disputed conclusions.
- CP-005/007 cannot be reduced to routine Redis harness work. Keep Astra on the
  failure model, but move contract-following implementation to Sol/high.
- P2B-003/005 do not automatically need Astra for every test run. Retain Sol with
  conditional escalation, provided the approved contract is unchanged.
- DEC items and P2B-008/PROD-001 cannot be closed by selecting a stronger model.
  Owner approval and external evidence remain separate requirements.
- SPEC-001/PROD-001 are too broad for a single confidence claim; split into
  measurable slices before using a lower-cost model as sole implementer.

Mechanical coverage check: all 26 open tracker IDs occur exactly once in the main
allocation table, with matching statuses. That proves coverage only, not 100%
correctness or an 87% success rate. Pilot v1 is recorded in
`evals/model_allocation/runs/pilot-v1/`. It had one under-specified task, one
critical first-pass failure and one infrastructure failure. No subagents were
launched and no live provider was contacted for this evaluation.

To measure the requested target rather than invent it:

- Define a successful task before testing: all required behavior and tests pass,
  no security/tenant/provenance violation, and no material reviewer correction.
- Start with 26 representative, held-out, bounded development tasks (not the 26
  blocked production tickets). Require at least 23 first-pass successes:
  23/26 = 88.46%, above an 87% observed-rate target. Count escalations/rework as
  first-pass failures; track their eventual outcome separately.
- This small-sample observed rate does not establish a population success rate
  of at least 87% with statistical confidence. A stronger claim needs a larger,
  preplanned stratified evaluation and a confidence interval.
- Include documentation, scoped implementation, migrations, tenant authorization,
  fault recovery, context and evaluation-design tasks. Record exact model/effort,
  prompt, repository revision, tool access, time and token usage.
- Review with tests and a reviewer who did not produce the answer. Critical
  authorization/isolation/replay defects fail the gate regardless of aggregate
  percentage. Keep architecture/security human review where required.
- Compare total usage per accepted task, including input, output, retries and
  reviewer tokens. Until measured, these assignments remain provisional.

The 87% empirical-quality target is **not yet verified**. Pilot v1 had 23/24
valid responses pass (95.83% observed; Wilson 95% interval 79.76–99.26%), but
also one critical failure, one invalid task and one infrastructure failure.
Its preregistered gate therefore fails. The results are too small and purposive
to estimate population reliability. They do not validate 87% correctness or
usage savings. See `evals/model_allocation/PROTOCOL.md` and the saved run.

## How to apply this without wasting usage

For the next item, WF-009, select `gpt-6-sol` with high reasoning and provide only
AGENTS.md, ACTION_ITEMS.md, the handoff, Phase 3 plan, relevant ADRs and tests.
Ask for an evidence/gap table, not a rewrite of the project. Escalate unresolved
architecture/exit claims to Astra with that table and the relevant code excerpts.

For later work, give the chosen model one bounded slice, acceptance tests,
authorized paths and relevant contracts. Use deterministic commands for counting,
formatting and measurements. Stop repeating an unsuccessful cheap-model attempt
after one diagnosis/retry; escalate with the observed failure. Do not restart
from the full conversation, run duplicate agents or use maximal effort by default.

This is a saved recommendation, not an automatic change to the active model,
account settings, billing tier, project router or deployment authorization.
