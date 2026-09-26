# Ryuk project-completion priorities

Date: 2026-09-26  
Status: owner sequencing and DEC-001 through DEC-003 selected; remaining policy decisions pending

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
   `moonshotai/kimi-k3` and `deepseek-ai/deepseek-v4-flash-0731`; served
   revisions and availability remain live evidence gates.
3. DEC-003 — DONE: all-class product scope; global regions subject to tenant and
   legal requirements; mandatory class-specific retention/deletion; no provider
   training; explicit provider/model disclosure. Activation remains evidence-gated.
4. DEC-004 — HOLD by owner: secret mechanism, hardware/access path and spending
   ceiling are deferred until live provider work is needed; no provider spend
   or credential use is currently authorized.
5. DEC-006 — REVIEW: public version-pinned repositories, synthetic Ryuk tasks,
   100+ held-out matched cases, 87% success, zero critical failures, five-point
   paired noninferiority margin and 25% all-in savings gate are approved; exact
   revisions, sealed manifest and independent reviewers remain to be recorded.
6. DEC-007: identity evidence required for live activation.
7. Scope decisions: first-release inclusion of multi-step workflows, tools,
   collaboration, persistent memory, specialist modalities, caching and HA.

No model or document may supply these owner decisions implicitly.

### P1 — controlled provider prerequisites

After P0, complete P2B-001 through P2B-005. These are bounded automated contract
checks needed to implement truthful tokenizer binding, cancellation and billing
behavior. They are not final acceptance or production rollout.

### P2 — core evidence-dependent build

1. CTX-003, then CTX-004.
2. WF-012 and WF-013.
3. WF-014 only if multi-step scope is approved.
4. TOOL-001, then COLLAB-001.
5. MEM-001.
6. One bounded SPEC-001 slice.
7. CACHE-001 after accepted-result and provenance policies are stable.

### P3 — production infrastructure and security

Complete CP-005, CP-006, CP-007 and SEC-001 if the approved deployment target
requires distributed/HA production infrastructure. Do not build distributed
components merely to satisfy a checklist if the approved first release is
single-controller.

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

Twenty-seven tracker items remain non-DONE: 18 HOLD (including deferred
EVAL-010), 8 BLOCKED and 1 REVIEW. Several broad items must be split after scope
decisions, so 27 is a lower bound on implementation change sets, not a schedule
estimate.
