# DEC-004 — Provider access and spending deferred

Date: 2026-09-26  
Status: deferred by owner

## Decision

The owner does not require provider credential delivery or a secret manager for
the current offline phase. Selection of a secret mechanism, provider account,
hardware/access path and spending ceiling is deferred until live provider work
is authorized in a future session.

## Current boundary

- Do not store or use provider credentials for Ryuk.
- Do not provision paid endpoints or hardware.
- Do not make live Ryuk provider calls or incur provider spend.
- Continue secret-free offline implementation with synthetic/public data under
  the existing project gates.

Previously shared chat credentials are not approved Ryuk credentials and must
not be copied into the repository, configuration, logs, reports or evaluation
artifacts.

## Reopening requirements

Before P2B-001 or any other credentialed provider work begins, the owner must
approve an access path, a non-repository secret-delivery mechanism, authorized
account/project ownership and explicit spending limits. That later approval
must not record credential values in Git.
