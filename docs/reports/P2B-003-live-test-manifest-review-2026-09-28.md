# P2B-003 bounded live-test manifest review

Date: 2026-09-28
Status: offline prerequisite implemented; P2B-003 remains blocked

## Implementation

`scripts/validate_phase2b_live_test_manifest.py` defines a closed, short-lived
preregistration packet for one Phase 2B ordinary-generation diagnostic. It is a
validator only and contains no provider client or execution path.

The contract binds the proposed diagnostic to:

- one exact approved model and one prompt digest;
- a lowercase 40-character Git revision;
- distinct SHA-256 references for the account evidence, new diagnostic
  hypothesis, owner approval and prompt;
- a timezone-aware validity window no longer than 24 hours;
- synthetic/public input and a USD 0 paid-spend ceiling;
- one attempt, concurrency one, no automatic retry or fallback, no streaming;
- at most a 300-second timeout and 256 requested output tokens; and
- mandatory stop conditions for payment/subscription, non-free entitlement,
  identity mismatch, unknown provider outcome and private/customer data.

The sanitized CLI output omits all four SHA-256 references. Invalid input
returns one generic error without echoing rejected content. A structurally valid
but expired manifest returns nonzero.

## Review

Twenty-three tests cover the valid path, summary redaction, unsafe top-level and
request settings, disabled stop conditions, extra fields, timestamp/validity
boundaries, strict type rejection, expiration, digest reuse, file loading,
non-echoing CLI errors and an independently supplied Git-revision mismatch.
Formatting, lint and strict typing pass for the implementation and tests.

The manifest does not prove that any referenced evidence, hypothesis or owner
approval exists or is authentic. A human reviewer must resolve and inspect
those references before a call. The validator does not make an inference call,
authorize one by itself, or change the current P2B-002/P2B-003 blocker. No live
manifest has been created because the required NVIDIA account evidence and new
diagnostic hypothesis are absent.

## Next use

After the P2B-002 account record is collected and reviewed:

1. write and retain a concrete new diagnostic hypothesis;
2. obtain explicit owner approval for one bounded call;
3. bind the evidence, hypothesis, approval, prompt and exact Git revision in a
   manifest;
4. run this validator with the independently resolved expected Git revision
   immediately before the separately reviewed probe; and
5. stop without calling the provider if the manifest is invalid or expired.
