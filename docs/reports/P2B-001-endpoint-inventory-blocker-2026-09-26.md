# P2B-001 endpoint inventory blocker

Date: 2026-09-26
Outcome: blocked before authenticated endpoint contact

## Scope and safety boundary

This check followed DEC-004's NVIDIA Developer Program boundary: free resources
only, a USD 0 paid-spend ceiling, synthetic/public data only, and no credential
values in commands, logs, reports, fixtures, or Git. No endpoint request,
provisioning action, subscription, or payment action was performed.

The approved local secret locator remains `env:NVIDIA_API_KEY`. Only the
environment variable's presence was checked; it was absent. No authenticated
browser surface was available, so account, project, entitlement, and endpoint
ownership could not be observed.

## Public catalog observations

Observed from NVIDIA's public catalog on 2026-09-26:

| Approved model ID | Shared catalog generation endpoint | Public free-endpoint state | Result |
| --- | --- | --- | --- |
| `moonshotai/kimi-k3` | `https://integrate.api.nvidia.com/v1/chat/completions` | Available | Public candidate only; account entitlement remains unobserved |
| `deepseek-ai/deepseek-v4-flash-0731` | `https://integrate.api.nvidia.com/v1/chat/completions` | Deprecated | Hard stop; the approved pair cannot be inventoried |

Sources:

- https://build.nvidia.com/moonshotai/kimi-k3?section=deploy
- https://build.nvidia.com/deepseek-ai/deepseek-v4-flash-0731
- https://build.nvidia.com/deepseek-ai/deepseek-v4-flash-0731/playground
- https://build.nvidia.com/deepseek-ai/deepseek-v4-pro-0813?nim=hosted
- https://build.nvidia.com/explore/reasoning
- https://docs.api.nvidia.com/nim/docs/run-anywhere
- https://docs.api.nvidia.com/nim/docs/api-quickstart

Public catalog advertising is not account-observed entitlement and does not
satisfy DEC-007. The shared URL plus different request model IDs also must not
be described as two independently certified endpoints before authenticated
account evidence establishes the provider's endpoint mapping.

The catalog's apparent successor, `deepseek-ai/deepseek-v4-pro-0813`, was not
selected automatically. NVIDIA's explore listings advertised it as a free
endpoint while its model deploy page reported the free endpoint deprecated.
That inconsistent public state reinforces the need for an explicit owner choice
and account-observed entitlement rather than a substitution based on search or
catalog labels.

A later public-catalog observation on 2026-09-26 found
`deepseek-ai/deepseek-v4.1-flash` advertised as the only DeepSeek-published
catalog result and as an available free endpoint. It is now the documented
DEC-009 recommendation; see
`docs/reports/DEC-009-deepseek-replacement-recommendation-2026-09-26.md`.
The owner subsequently approved that exact replacement in DEC-009. This public
observation still does not establish account entitlement.

## Historical blocking decision

DEC-009 resolved the deprecated-model decision. P2B-001 remains blocked because
the authorized account entitlement cannot be observed without a protected
`NVIDIA_API_KEY` injection or an already authenticated account surface. It must
stop if the account requests payment, paid credits, a subscription, or paid
provisioning.

This was the state at the time of the blocked attempt. The later authenticated
inventory resolved the credential/account-visibility blocker and completed
P2B-001; see
`docs/reports/P2B-001-authorized-endpoint-inventory-2026-09-26.md`.
