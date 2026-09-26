# DEC-003 — Data classification and governance

Date: 2026-09-26  
Status: partially approved by owner

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

## Current activation boundary

The existing synthetic/public-only restriction remains in force for offline
development and any future provider checks until the remaining DEC-003 rules
and their required controls are approved. No private, customer, confidential,
regulated, personal or credential-bearing data is authorized by this partial
decision.

## Decisions still required

DEC-003 remains in `REVIEW` until the owner specifies:

- permitted processing and storage regions, including cross-border behavior;
- retention and deletion periods by data class;
- provider retention and training-use constraints; and
- when and how users must be told which provider/model processes their data.

The resulting policy must identify any classes that require separate legal,
contractual or organizational approval before activation. No model or
implementation may invent those approvals.
