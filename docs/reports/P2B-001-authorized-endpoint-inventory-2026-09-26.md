# P2B-001 authorized NVIDIA endpoint inventory

Date: 2026-09-26
Outcome: complete for endpoint inventory; generation certification remains open

## Scope and safety boundary

This check used the owner-approved NVIDIA Developer Program boundary from
DEC-004: free resources only, a USD 0 paid-spend ceiling, synthetic/public data
only, and no credential material in Git, commands, logs, reports, fixtures, or
test output. The credential was supplied only through `env:NVIDIA_API_KEY`.

No generation, provisioning, subscription, payment, or paid-resource request
occurred. The authenticated operation was a read-only `GET /v1/models` request.

## Sanitized authenticated observation

Observed at `2026-09-27T01:52:48.706417+00:00` against:

- API origin: `https://integrate.api.nvidia.com`
- Catalog route: `GET /v1/models`
- Authentication: bearer credential obtained from `env:NVIDIA_API_KEY`
- HTTP result: `200`
- Response media type: `application/json`

The authenticated catalog returned both owner-approved exact model IDs:

| Approved model route | Catalog object | Catalog owner | Result |
| --- | --- | --- | --- |
| `moonshotai/kimi-k3` | `model` | `moonshotai` | visible to the authenticated account |
| `deepseek-ai/deepseek-v4.1-flash` | `model` | `deepseek-ai` | visible to the authenticated account |

Both model routes use NVIDIA's shared hosted API origin. This report does not
claim that they are separate physical endpoints, deployments, runtimes, model
weights, or hardware allocations. It establishes the exact authorized catalog
routes and account-visible access needed to start the controlled Phase 2B
contract checks.

## Decision

P2B-001 is complete. Its two blockers are resolved:

1. DEC-009 approved `deepseek-ai/deepseek-v4.1-flash` as the replacement for
   the deprecated DeepSeek target.
2. The protected credential successfully authenticated and the authorized
   catalog exposed both exact approved model IDs.

This evidence does not satisfy P2B-002 or DEC-007 activation. The next checks
must independently record authentication/readiness behavior, exact generation
response identity, and sanitized provider catalog/dashboard mapping without
claiming artifact-verified model weights. All checks must stop on payment,
subscription, paid provisioning, exhausted credits, missing free entitlement,
or ambiguous pricing.

## Secret-handling review

- The credential value was never printed or written to the repository.
- No authorization header or sensitive response header was recorded.
- Only the status, observation timestamp, and three non-secret catalog fields
  (`id`, `object`, and `owned_by`) for the two approved targets were retained.
- No `.env` file was created.
