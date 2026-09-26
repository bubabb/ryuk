# DEC-001 — Hosted-first initial release

Date: 2026-09-26  
Status: approved by owner

## Decision

Ryuk's first certified release will be hosted-first. The Ryuk API, control plane,
workflow state and vendor-independent interfaces remain self-managed. Initial
inference will use explicitly authorized hosted NVIDIA endpoints through
Ryuk-owned adapters.

## Rationale

Hosted inference shortens the path to measured model behavior without making a
specific provider protocol Ryuk's internal architecture. It avoids requiring
self-hosted GPU operations before the first complete product slice while
preserving a later self-hosted deployment option behind the same Ryuk
interfaces.

## Approved environment boundary

- Self-managed Ryuk controller and development/test services.
- Authorized hosted NVIDIA inference endpoints for the initial model profiles.
- Synthetic/public inputs only until DEC-003 approves broader data handling.
- No production activation merely from this decision.

Exact model revisions remain DEC-002. Region, residency, retention and provider
disclosure remain DEC-003. Credentials, secret delivery, account/project,
hardware fallback and spending ceiling remain DEC-004. Exact endpoints and live
readiness remain P2B-001/P2B-002, and live identity acceptance remains DEC-007.

## Consequences

- P2B-001 should inventory hosted endpoints, not provision self-hosted inference
  as the first path.
- Hosted-provider behavior must be measured; catalog names and compatibility
  claims are not certification.
- Self-hosted engines remain architectural targets and may be added later
  without replacing Ryuk's internal request/engine/response abstractions.
