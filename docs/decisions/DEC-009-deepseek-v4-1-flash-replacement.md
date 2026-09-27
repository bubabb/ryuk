# DEC-009 — DeepSeek V4.1 Flash replacement

Date: 2026-09-26
Status: approved by owner

## Decision

Replace the deprecated initial hosted candidate
`deepseek-ai/deepseek-v4-flash-0731` with the exact NVIDIA catalog identifier
`deepseek-ai/deepseek-v4.1-flash`.

The initial hosted pair is now:

- `moonshotai/kimi-k3`
- `deepseek-ai/deepseek-v4.1-flash`

## Evidence boundary

The owner approved the replacement after review of
`docs/reports/DEC-009-deepseek-replacement-recommendation-2026-09-26.md`.
NVIDIA's public catalog advertised the replacement as a free endpoint on the
decision date. This decision does not establish account entitlement, endpoint
ownership, served revision, artifact identity, runtime identity, or successful
inference.

The published hosted chat schema does not expose the model card's numeric
reasoning-effort control. Ryuk must not translate its named reasoning settings
to numeric values without contract evidence. P2B testing must verify reasoning,
structured output, tools, limits, cancellation, and response fields.

## Consequences

- Add a new immutable offline candidate profile and sanitized contract fixture.
- Retain the deprecated `-0731` profile and fixture as historical evidence,
  outside the active offline candidate set.
- Admit the new exact ID in the hosted NVIDIA adapter while retaining the old
  ID for historical replay compatibility.
- Do not activate either hosted candidate until P2B evidence satisfies DEC-007.
- Paid use remains prohibited by DEC-004's USD 0 ceiling.
