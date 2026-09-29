# Phase 2B certification blocker review

Date: 2026-09-28
Outcome: implementation and collected evidence reviewed; external certification remains blocked

## Review scope

This review reconciles P2B-001 through P2B-008 against their recorded
dependencies and the sanitized evidence under `evidence/phase2b/`. It does not
make a new inference request, spend money, activate a deployment or weaken an
acceptance gate.

The review also rechecked NVIDIA's current public catalog pages for
[`moonshotai/kimi-k3`](https://build.nvidia.com/moonshotai/kimi-k3) and
[`deepseek-ai/deepseek-v4.1-flash`](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash).
They advertise both routes as available free endpoints, but public catalog
availability is not the account-specific catalog/dashboard mapping required by
DEC-007 and cannot replace live response evidence.

## Item disposition

| Item | Disposition | Evidence or blocker |
| --- | --- | --- |
| P2B-001 | `DONE` | Authenticated catalog inventory returned both approved model IDs. |
| P2B-002 | `BLOCKED` | DeepSeek response identity was observed. Kimi returned no response identity, and the required authenticated account/dashboard mapping is unavailable because this session has no browser surface. |
| P2B-003 | `BLOCKED` | One small DeepSeek point passed. Two larger DeepSeek boundary points failed and all bounded Kimi generation attempts timed out. Another call is prohibited until a new provider/account diagnostic explains readiness and queue behavior. |
| P2B-004 | `BLOCKED` | Client timeouts and local cancellation are recorded, but no provider cancellation acknowledgment, late-result channel, real malformed response, natural overload or live HTTP 202/request ID was observed. Artificial load is prohibited. |
| P2B-005 | `BLOCKED` | DeepSeek tool proposal and prompt-constrained JSON passed. Provider-enforced structured output and Kimi advanced capabilities remain unverified; more Kimi calls are prohibited before ordinary generation works. |
| P2B-006 | `BLOCKED` | P2B-002 through P2B-004 are incomplete, so real failover would risk replaying unknown provider work. |
| P2B-007 | `BLOCKED` | P2B-003 has no stable two-profile operating envelope; the pinned benchmark also requires the separately governed corpus/readiness evidence. |
| P2B-008 | `BLOCKED` | Its P2B-002 through P2B-007 prerequisites are incomplete, and final activation/rejection requires owner sign-off. |

## Required external unblock evidence

1. An authenticated, sanitized NVIDIA account/dashboard or provider-support
   record mapping the account and endpoint to both exact configured routes,
   including Kimi entitlement/readiness and recent-request disposition.
2. Provider evidence explaining whether the unacknowledged Kimi requests were
   queued, rejected, completed asynchronously or discarded, and how any request
   ID/status and cancellation contract works for this account.
3. A new, reviewable diagnostic hypothesis before any repeated Kimi inference
   or failed DeepSeek boundary request. The USD 0 ceiling remains binding.
4. Naturally observed or provider-supplied overload, malformed-response,
   cancellation-acknowledgment and late-result evidence; do not manufacture
   load to obtain it.
5. Stable ordinary generation for both profiles before failover or benchmark
   execution, followed by the DEC-006 benchmark inputs, independent roles and
   explicit run approval.
6. Owner review of the complete evidence set before P2B-008 activation or
   rejection. Missing evidence must remain unknown rather than being inferred
   from advertised capabilities.

## Correctness conclusion

The existing implementation correctly fails closed on unknown identity,
timeouts, local cancellation, malformed output and asynchronous pending
responses. Sanitized evidence does not retain credentials, headers, prompts,
outputs, reasoning, provider IDs or response bodies. The current obstacle is
external evidence and stable provider behavior, not an unimplemented local
retry or activation path. Adding automatic retries, polling or failover now
would weaken the recorded safety model and is therefore not a valid completion
strategy.

Phase 2B is not complete. Its tracker now uses `BLOCKED` rather than `IN
PROGRESS` for P2B-002 through P2B-005 so future sessions do not repeat unsafe or
uninformative requests while the named evidence remains unavailable.
