# DEC-002 — Initial hosted model targets

Date: 2026-09-26  
Status: approved by owner

## Decision

Ryuk's initial hosted-first release targets these two exact provider catalog
model identifiers:

- `moonshotai/kimi-k3`
- `deepseek-ai/deepseek-v4-flash-0731`

These identifiers bind the initial model choices and the existing offline
deployment profiles. No substitute model or silent revision is approved by this
decision.

## Evidence boundary

This is a product-selection decision, not evidence that either model is
currently available, accessible, or served by a particular endpoint. Hosted
runtime, engine, image, tokenizer/template and artifact revisions remain
unknown unless the provider exposes evidence that satisfies the applicable
live gates.

P2B-001 must inventory the exact authorized endpoints. P2B-002 must verify
authentication, readiness and served-model identity. DEC-007 must define which
live identity evidence is sufficient for activation. Any provider-side alias,
replacement or material revision requires explicit review rather than being
treated as the approved model automatically.

## Consequences

- The two existing offline profiles remain the initial candidates.
- Tests and configuration must continue to reject unapproved model IDs.
- Catalog names must not be represented as immutable weight, artifact or
  runtime identity.
- No endpoint call, credential use, spend or production activation is
  authorized by this decision.
