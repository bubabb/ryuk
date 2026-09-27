# DEC-009 DeepSeek replacement recommendation

Date: 2026-09-26
Outcome: approved by owner; decision recorded in
`docs/decisions/DEC-009-deepseek-v4-1-flash-replacement.md`

## Recommendation

Replace the deprecated initial target
`deepseek-ai/deepseek-v4-flash-0731` with the exact NVIDIA catalog identifier
`deepseek-ai/deepseek-v4.1-flash`.

The owner approved this recommendation on 2026-09-26. The decision record,
replacement profile, fixture, and allowlist update are maintained separately so
this report remains the pre-decision evidence record.

## Public catalog evidence

NVIDIA's public catalog was observed on 2026-09-26:

| Candidate | Public free-endpoint state | Relevant catalog description | Decision relevance |
| --- | --- | --- | --- |
| `deepseek-ai/deepseek-v4.1-flash` | Available | DeepSeek-published 552B MoE, 8B active, 1M context, text/image input and text output | Recommended current successor |
| `deepseek-ai/deepseek-v4-flash-0731` | Deprecated | Previously approved 284B MoE, 1M context, text input/output | Cannot satisfy hosted-first free-endpoint scope |
| `deepseek-ai/deepseek-v4-flash` | Deprecated | 284B MoE, 1M context, coding and agents | Moving alias is not a viable free endpoint |
| `deepseek-ai/deepseek-v4-pro-0813` | Deprecated | 1.65T MoE, 262K context, coding and reasoning | Not a viable free-endpoint replacement |

Sources:

- https://build.nvidia.com/models?q=deepseek
- https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash/build
- https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash/playground
- https://build.nvidia.com/deepseek-ai/deepseek-v4-flash-0731
- https://build.nvidia.com/deepseek-ai/deepseek-v4-flash/deploy
- https://build.nvidia.com/deepseek-ai/deepseek-v4-pro-0813?nim=hosted

The public catalog currently lists only one DeepSeek-published result and marks
`deepseek-ai/deepseek-v4.1-flash` as a free endpoint. This is public catalog
evidence only. It does not establish account entitlement, endpoint ownership,
served revision, artifact identity, runtime identity, or successful inference.

## Compatibility impact requiring implementation after approval

The replacement is not merely a spelling change. Its published contract adds
image input and describes a different architecture and active-parameter count.
Approval should trigger a new immutable deployment profile and sanitized
contract fixture rather than mutation of the historical `-0731` profile.
Adapter-local request/response behavior, reasoning fields, structured output,
tool use, context limits, and identity evidence must be re-verified. Historical
attempts must continue resolving the old deployment/model attribution.

## Required owner decision

Approve `deepseek-ai/deepseek-v4.1-flash` as the second initial hosted candidate,
or name a different exact catalog ID/revise the two-deployment target. Approval
does not authorize paid use and does not complete P2B-001; protected account
evidence is still required under DEC-004 and DEC-007.
