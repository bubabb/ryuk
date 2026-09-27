# DEC-004 — Developer Program access and spending policy

Date: 2026-09-26
Status: accepted

## Decision

Ryuk will use NVIDIA Developer Program free resources for development,
prototyping, testing, and evaluation. The default paid-spend ceiling is exactly
USD 0. Paid services may be considered later only through a separate explicit
owner approval that names the service, purpose, account, duration, and maximum
spend; this decision does not pre-authorize that expansion.

For controlled Phase 2B checks, an operator may inject the NVIDIA credential
through a protected local environment variable. A repository secret manager is
not required at this phase. Credential values must never enter Git, chat,
fixtures, command arguments, logs, reports, or test output.

## Current boundary

- Use only NVIDIA-hosted resources visibly covered by the account's Developer
  Program free allowance.
- Stop before any action that requests payment, a subscription, paid credits,
  or paid cloud/GPU provisioning.
- Keep the account/project owner-controlled and the credential outside the
  repository, supplied only at execution time through the documented local
  environment-variable name.
- Limit current Phase 2B inputs to synthetic/public data. This authorization
  does not enable production traffic or private/customer data.
- Treat credit exhaustion, entitlement absence, or ambiguous pricing as a hard
  stop, never as permission to fall through to paid usage.

Previously shared chat credentials are not NVIDIA credentials approved for
Ryuk and must not be copied into the repository, configuration, logs, reports,
or evaluation artifacts.

## Expansion requirements

Any move beyond free Developer Program resources requires a new recorded owner
decision. That decision must establish a non-repository production-grade secret
mechanism, authorized account/project and billing owner, exact service and
region, a finite monetary ceiling, monitoring and stop behavior, and applicable
production/data-governance approval. It must not record credential values in
Git.

NVIDIA's current NIM documentation states that Developer Program members have
free hosted endpoint access for prototyping and free downloadable NIM access
for research, development, and testing, subject to program scope and limits:
https://docs.api.nvidia.com/nim/docs/product. Availability and entitlement must
still be observed on the authorized account during P2B-001/P2B-002.
