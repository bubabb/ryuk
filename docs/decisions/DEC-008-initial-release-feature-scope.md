# DEC-008 — Initial release feature scope

Date: 2026-09-26  
Status: approved by owner

## Included in the initial certified release

- Multi-step workflow dependency graphs.
- Governed, isolated tool execution.
- Scoped persistent memory with evidence and deletion semantics.
- Provenance-preserving application result caching.

Inclusion defines required release scope; it does not waive each feature's
architecture, security, dependency, test, evaluation or certification gates.

## Deferred until after the initial certified release

- Multi-agent Kimi–DeepSeek collaboration.
- Specialist modality vertical slices.
- High-availability Redis/database operation and its associated failover,
  partition, migration and restore certification.

The deferred capabilities remain roadmap items. They are not required to call
the bounded initial release complete and must not be represented as implemented
or certified in that release.

## Consequences

WF-014's product-scope gate is satisfied and it may proceed as the next bounded
offline design/implementation task. TOOL-001, MEM-001 and CACHE-001 remain held
until their recorded phase and technical prerequisites are met. COLLAB-001,
SPEC-001 and CP-005 through CP-007 remain post-release HOLD items.
