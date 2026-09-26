# DEC-003 — Data classification and governance

Date: 2026-09-26  
Status: approved by owner

## Approved product scope

Ryuk is intended to support all data classifications, including public,
synthetic, internal, private, customer, confidential and regulated data. The
system must not be designed with a permanent synthetic/public-only product
limitation.

Support in the product roadmap is not blanket authorization to process every
class immediately. A deployment may admit a class only when its applicable
security, contractual, privacy, residency, retention, deletion, audit and
access-control requirements have been defined and verified. Unsupported or
unverified classes must fail closed.

## Governance policy

- Processing and storage may use global regions only when the tenant's policy
  and applicable legal, contractual and regulatory requirements permit the
  selected locations and cross-border path.
- Retention and deletion periods are configurable by tenant and data class. A
  deployment must define them before admitting non-public data; absence of a
  valid policy fails closed.
- Providers must not train on submitted data. A provider whose applicable
  terms or configuration cannot establish that boundary is ineligible for the
  affected data.
- The processing provider and model must be disclosed explicitly to the user
  or tenant before processing. Substitution requires equivalent disclosure and
  must satisfy the same policy.

Ryuk must carry the applicable classification and governance policy through
admission, routing, storage, logs, artifacts, deletion and audit evidence. A
globally capable product does not imply that every region or provider is valid
for every tenant or data class.

## Current activation boundary

The existing synthetic/public-only restriction remains in force for offline
development and provider checks until implementations enforce this policy and
the applicable tenant, provider and jurisdiction evidence is verified. No
private, customer, confidential, regulated, personal or credential-bearing
data is authorized merely by completing this product decision.

Individual deployments may still require separate legal, contractual or
organizational approval. No model or implementation may invent those approvals.
