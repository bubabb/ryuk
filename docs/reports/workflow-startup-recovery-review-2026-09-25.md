# WF-011 startup recovery review

Date: 2026-09-25  
Scope: opt-in offline SQLite workflow service

## Decision

WF-011 is complete for the approved offline scope. Application startup now
runs bounded recovery before runtime-state collection, fences expired leases,
reconciles only valid durable outcomes, and retains unknown or invalid evidence
as `uncertain`. A governed operator route exposes a tenant-filtered report.
There is no automatic inference replay.

## Review findings

The review checked transaction rollback, fence relationships, artifact
creation, idempotent repeated recovery, startup ordering, resource cleanup,
tenant isolation and route authorization. It found one in-process restart edge:
an older recovery report could remain if a later startup failed before
assignment. The final implementation clears the report at lifespan entry and a
failure-path test proves it stays unavailable while resources close.

No unresolved correctness defect remained after that fix. Exact-route tests
prove inference-role callers are rejected, operator results exclude another
tenant, and a missing startup report fails closed. A scan-limit overflow rolls
back before any workflow transition. Corrupt journal evidence creates no
artifact and remains uncertain with `invalid_outcome_evidence`.

## Limits

This does not start WF-010's dispatcher, contact providers, validate recovered
outputs, cancel calls, or resolve genuinely unknown outcomes. The in-memory
startup report is reset on each lifespan and is not a durable notification or
incident ledger. Distributed recovery and production operations remain future
work.

## Verification

Focused startup/recovery/API tests: 50 passed. Full offline suite: 400 passed
and 8 external integrations deselected. Ruff passed; Mypy passed across 110
sources; compileall, `git diff --check` and a repository scan for pasted
API-key patterns passed.
