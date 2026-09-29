# P2B-004 failure-evidence intake review

Date: 2026-09-28
Status: offline evidence boundary implemented; P2B-004 remains blocked

## Implementation

`scripts/validate_nvidia_failure_evidence.py` validates a closed, sanitized
record for one failure-behavior claim. Accepted source classes are authenticated
dashboard, provider support, naturally observed response and official
documentation. Accepted event classes are asynchronous pending, acknowledged
cancellation, late result, malformed response and overload.

The schema retains only the exact model, event/evidence classification,
allowlisted status code, provider-acknowledgment flag, coarse request and
execution disposition, late-result state, retry-after presence, timestamp and
hash references. It has no fields for credentials, headers, request IDs,
prompts, outputs, reasoning, response/error bodies, screenshots or support
text. Its printed summary omits the account and source-artifact hashes.

Semantic validation rejects:

- asynchronous-pending claims without HTTP 202 and a pending disposition;
- acknowledged cancellation without provider acknowledgment and a cancelled
  disposition;
- late-result claims without an observed late result;
- malformed-response claims based only on documentation;
- overload claims without HTTP 429 or 503;
- documentation that claims observed execution termination or a late result;
- official documentation marked as observed behavior;
- naturally observed responses marked as documentation;
- account-specific sources without a hashed account reference;
- raw/invalid or reused references, naive timestamps and unknown fields.

Invalid CLI input produces one generic error and does not echo rejected
provider content.

## Review

Thirteen tests cover sanitized valid evidence, every event-specific
contradiction, contract-versus-observation separation, source-level agreement,
account/hash rules, extra/raw data rejection, timestamp handling, file loading
and non-echoing CLI errors. Formatting, lint and strict typing pass.

This contract validates the shape and internal consistency of supplied
evidence. It does not authenticate a hash reference, contact NVIDIA, cancel a
request, poll an asynchronous result, generate overload, or establish provider
behavior that was not observed. A successful validation is not by itself enough
to close P2B-004.

## Next use

When a non-disruptive provider/support record or natural failure is available,
retain the source artifact outside Git, create the sanitized record, run the
validator, and review the source plus summary together. Never create artificial
provider load to obtain an overload event and never infer provider termination
from local client closure.
