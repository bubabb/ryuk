# DEC-007 — Live hosted model identity

Date: 2026-09-26  
Status: approved by owner

## Decision

Ryuk may accept provider-attested identity for an opaque hosted endpoint when
all of the following evidence agrees:

- the authorized endpoint configuration names the exact DEC-002 model ID;
- a live authenticated response reports the matching served-model ID;
- the provider catalog or account dashboard independently confirms the endpoint
  mapping; and
- the evidence records the endpoint reference, sanitized account/project
  reference and observation timestamp.

Any mismatch, unapproved alias, missing observation or unverifiable mapping
fails closed. Substitution requires a separate approval rather than silently
inheriting authorization from the original model.

## Claim boundary

Passing this policy establishes provider-attested served identity. It does not
establish a cryptographically verified weight, artifact, tokenizer, runtime or
engine identity when the hosted provider does not expose that evidence. Ryuk
must preserve those unknowns and must not describe catalog/dashboard agreement
as weight verification.

## Activation boundary

This decision defines acceptable identity evidence but does not provide it.
DEC-004 now authorizes only NVIDIA Developer Program free-resource checks with
a USD 0 paid-spend ceiling and protected local credential injection. P2B-001
must inventory the account-authorized endpoints, and P2B-002 must then collect
and validate the live evidence for each exact endpoint before activation.
