# Ryuk project-completion priorities

Date: 2026-09-26  
Status: DEC-001 through DEC-009 and P2B-001 complete; P2B-002 is next

## Selected delivery sequence

The owner selected this high-level order:

1. Complete the product build as far as truthful offline and contract evidence
   permits.
2. Run the evaluation program after the offline build-completion gate.
3. Perform final hands-on real-time acceptance and production certification.

“Build complete” does not mean externally certified. Some implementation items
depend on verified provider behavior and therefore cannot be marked `DONE`
before controlled real-provider contract checks. Those prerequisite checks are
not the final hands-on acceptance phase and must not be replaced by assumptions.

## Priority order

### P0 — owner decisions

Resolve these before implementation branches diverge:

1. DEC-001 — DONE: hosted-first; self-managed Ryuk controller with authorized
   hosted NVIDIA inference endpoints.
2. DEC-002 — DONE: exact initial hosted catalog targets are
   `moonshotai/kimi-k3` and, as superseded by DEC-009,
   `deepseek-ai/deepseek-v4.1-flash`; served revisions and availability remain
   live evidence gates.
3. DEC-003 — DONE: all-class product scope; global regions subject to tenant and
   legal requirements; mandatory class-specific retention/deletion; no provider
   training; explicit provider/model disclosure. Activation remains evidence-gated.
4. DEC-004 — DONE: use NVIDIA Developer Program free resources with protected
   local environment injection and a USD 0 paid-spend ceiling. Paid expansion
   requires a separate explicit owner decision with a finite cap.
5. DEC-006 — DONE: public version-pinned repositories plus synthetic Ryuk
   tasks, 100+ held-out matched cases, 87% success, zero critical failures,
   five-point paired noninferiority margin and 25% all-in savings gate are
   approved. EVAL-010 must freeze exact revisions, sealed cases and named
   independent people after the offline build-completion gate.
6. DEC-007 — DONE: exact endpoint configuration/live-response agreement plus
   independent provider catalog/dashboard mapping and timestamped sanitized
   evidence; mismatches fail closed and weight identity remains unverified.
7. DEC-008 — DONE: initial release includes multi-step workflows, governed
   tools, persistent memory and caching; collaboration, specialist modalities
   and HA are deferred until after initial certification.
8. DEC-009 — DONE: replace the deprecated DeepSeek candidate with exact catalog
   ID `deepseek-ai/deepseek-v4.1-flash`; account entitlement remains a live
   evidence gate.

No model or document may supply these owner decisions implicitly.

### P1 — controlled provider prerequisites

After P0, complete P2B-001 through P2B-005. These are bounded automated contract
checks needed to implement truthful tokenizer binding, cancellation and billing
behavior. They are not final acceptance or production rollout.

### P2 — core evidence-dependent build

1. CTX-003, then CTX-004.
2. WF-012 and WF-013.
3. WF-014 — DONE: bounded dependency-graph and scheduler-state contracts.
4. WF-015 — DONE: schema v6 durable graph/node state and atomic causal readiness.
5. WF-016 — DONE: fenced graph execution, accepted-artifact binding and a
   durable graph-wide budget. WF-017 — DONE: governed APIs, explicit local
   dispatch, fenced cancellation and no-replay startup recovery.
6. TOOL-001 after its phase gate.
7. MEM-001.
8. CACHE-001 after accepted-result and provenance policies are stable.

COLLAB-001 and SPEC-001 are post-initial-release work under DEC-008.

### P3 — production infrastructure and security

CP-005, CP-006 and CP-007 are post-initial-release HA work under DEC-008.
SEC-001 remains gated by the future production deployment and DEC-004 access
design. Do not build distributed components merely to satisfy a checklist.

### P4 — evaluation

Resume EVAL-010, freeze the v3 protocol, curate the held-out corpus, execute the
matched evaluation, and run the context/tool/collaboration/memory/specialist/
cache suites applicable to the approved first-release scope. Fix failures before
certification.

### P5 — real-time certification and owner acceptance

Complete P2B-006 through P2B-008 and PROD-001: failover, quality/performance/cost,
load, soak, chaos, restore, security, canary, rollback, incident readiness and
hands-on owner acceptance. Only this stage can support a production-readiness
claim.

## Current count

Twenty-two tracker items remain non-DONE: 15 HOLD (including deferred
EVAL-010), 4 READY, and 3 BLOCKED. P2B-002 through P2B-005 are the next
controlled provider-contract sequence.
Several broad items must be split after
scope decisions, so 24 is a lower bound on implementation change
sets, not a schedule estimate.
