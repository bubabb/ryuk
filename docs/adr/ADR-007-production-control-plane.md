# ADR-007: Production Control Plane

- Status: Accepted architecture; distributed production rollout gated
- Date: 2026-08-31

## Decision

Ryuk separates the inference data path from an authenticated, tenant-scoped
control plane. Authentication establishes a server-owned `Principal`; clients
cannot assert tenant identity or roles. Every object and function access checks
tenant plus role and denies by default. Admission occurs before model execution
and limits request rate, concurrency, and estimated tokens.

Execution records are append-oriented, versioned, tenant-keyed, and contain
routing, attempt, provenance, audit, and evaluation data without credentials.
The included SQLite/WAL implementation is a durable reference and local recovery
target. Multi-replica production requires a transactional external store and a
distributed quota coordinator implementing the same boundaries.

Secrets are locators (`SecretRef`) resolved by a deployment secret manager;
secret values never enter configuration examples, provenance, records, or
telemetry. Restricted data cannot be payload-logged. Governance policy binds
classification, retention, and allowed locations.

Deployments use a fail-closed lifecycle: draft, validating, ready, active,
draining, retired/failed. Activation requires verified artifact digest,
signature/provenance, vulnerability scan, compatibility tests, and deployment
identity. Invalid transitions are rejected.

## Operations and recovery

- Structured events exclude prompts, outputs, credentials, and secrets by default.
- Schema version is checked on startup; unknown versions fail startup.
- Backups use a consistent database snapshot and must be restored in a scheduled drill.
- Load tests prove quota/deadline behavior; soak tests cover leaks and drift;
  chaos tests cover dependency failures without cross-tenant access.
- Production requires alerting, key rotation, encryption, external secret
  resolution, supply-chain scanning, restore RPO/RTO evidence, and multi-replica
  admission tests. These are deployment gates, not code defaults.

This design addresses authorization and resource consumption risks in the
[OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).
