# ADR-020: Conservative startup workflow recovery

Date: 2026-09-25  
Status: Accepted for the offline single-controller reference slice

## Context

Ryuk already persists dispatch intent and outcomes and can mark an expired lease
uncertain. Those operations were explicitly invoked in tests or by internal
callers. Restarting the opt-in workflow service did not automatically inspect
expired work, reconcile saved outcomes, or expose unresolved work to an
authorized operator.

## Decision

When and only when the offline workflow store is configured, application
lifespan runs one bounded recovery transaction before starting runtime-state
collection. The transaction selects existing uncertain workflows and running
work whose leases have expired.

Expired work is fenced and moved to `uncertain`. A workflow is completed only
when its matching dispatch journal contains a valid, hash-matching persisted
outcome with the expected fence relationship and success marker. Missing or
invalid evidence remains uncertain with a stable reason code. Recovery never
calls the inference router, creates a new attempt, validates output, or starts
the local dispatcher.

`WORKFLOW_RECOVERY_SCAN_LIMIT` bounds the transaction. If the candidate set
exceeds it, the transaction rolls back and application startup fails. A failed
startup clears any in-process report from an earlier lifespan before doing
work, preventing stale recovery status.

The completed report is available through `GET /v1/workflows/recovery` to the
existing operator/admin role. Results are filtered to the authenticated
principal's tenant and contain workflow IDs, terminal/recovery states, and
stable reason codes only. The route uses normal admission and terminal-record
governance; it exposes no prompt, result, journal payload, provider detail or
cross-tenant count.

## Consequences and limits

- Restart can conservatively recover saved outcomes without provider replay.
- Unresolved and corrupt evidence stays operator-visible and nonterminal.
- The SQLite transaction is suitable only for the current offline reference
  store. It is not a distributed recovery coordinator or production claim.
- There is no provider lookup/cancellation, forced dispatcher shutdown, lease
  renewal, automatic validation, notification channel or remediation action.
- Production configuration still rejects this offline workflow subsystem.
