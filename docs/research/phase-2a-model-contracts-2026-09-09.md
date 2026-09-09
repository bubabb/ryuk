# Phase 2A Model and Contract Identification — 2026-09-09

## Decision scope

This note identifies two offline candidate profiles for contract development. It
does not select hosted-first deployment, authorize provider access, certify an
endpoint, or mark either model production-eligible.

The initial shared adapter boundary is the NVIDIA hosted API catalog because it
currently exposes both candidates through one documented deployment family.
Direct DeepSeek, Moonshot, and self-hosted profiles remain separate possible
deployments and must not reuse hosted identity evidence.

## Candidate 1 — Kimi K3 on NVIDIA hosted NIM

| Field | Recorded value |
| --- | --- |
| Provider model identifier | `moonshotai/kimi-k3` |
| Candidate endpoint | `https://integrate.api.nvidia.com/v1/chat/completions` |
| Interface boundary | Adapter-local OpenAI-compatible chat completion |
| Input modalities | Text and image |
| Output modality | Text |
| Advertised context | 1,048,576 tokens |
| Reasoning effort | `low`, `high`, `max`; thinking always enabled |
| Advertised features | Multiturn chat, system prompts, tools, structured output, preserved reasoning history |
| Required conversation behavior | Return complete prior assistant reasoning content and tool calls on later turns |
| Hosted geography statement | Global |
| Artifact/runtime/hardware evidence from hosted request | Unknown until Phase 2B; do not infer from the downloadable model card |

Primary sources checked on 2026-09-09:

- NVIDIA API catalog model and request example:
  <https://build.nvidia.com/moonshotai/kimi-k3>
- NVIDIA model card:
  <https://build.nvidia.com/moonshotai/kimi-k3/modelcard>

The catalog currently distinguishes downloadable, free hosted, and partner
availability. Those are separate deployment modes, not one interchangeable
profile.

## Candidate 2 — DeepSeek V4 Flash 0731 on NVIDIA hosted NIM

| Field | Recorded value |
| --- | --- |
| Provider model identifier | `deepseek-ai/deepseek-v4-flash-0731` |
| Candidate endpoint | `https://integrate.api.nvidia.com/v1/chat/completions` |
| Interface boundary | Adapter-local OpenAI-compatible chat completion |
| Input modality | Text |
| Output modality | Text plus separately represented reasoning content where returned |
| Advertised context | 1,000,000 tokens |
| Reasoning effort | `low`, `high`, `max` through adapter-local parameters |
| NVIDIA example settings | `temperature=1`, `top_p=0.95`, `max_tokens=16384`, thinking enabled, high reasoning effort |
| Hosted geography statement | Global |
| Download availability | Reported unavailable for this exact NVIDIA catalog profile |
| Artifact/runtime/hardware evidence from hosted request | Unknown until Phase 2B |

Primary sources checked on 2026-09-09:

- NVIDIA API catalog model and request example:
  <https://build.nvidia.com/deepseek-ai/deepseek-v4-flash-0731>
- NVIDIA model card:
  <https://build.nvidia.com/deepseek-ai/deepseek-v4-flash-0731/modelcard>
- DeepSeek's direct API documentation, used only to distinguish the direct
  provider deployment from NVIDIA's hosted identifier:
  <https://api-docs.deepseek.com/>

DeepSeek's direct API uses moving aliases such as `deepseek-v4-flash` and
`deepseek-v4-pro`. Those aliases are not authoritative identities for NVIDIA's
revision-bearing `deepseek-ai/deepseek-v4-flash-0731` candidate.

## Contract decisions for offline implementation

1. Use the exact revision-bearing identifiers above in offline hosted profiles.
2. Keep the external chat-completion schema inside `NVIDIAHostedNIMEngine`.
3. Model both candidates as chat deployments; Kimi additionally needs a later
   multimodal vertical slice rather than an untyped message payload.
4. Preserve reasoning output separately when the endpoint returns it. Do not
   concatenate hidden/reasoning content into ordinary answer text implicitly.
5. Treat context length, tools, structured output, streaming, cancellation,
   token usage, and reasoning controls as advertised claims until contract tests
   or Phase 2B observations establish the exact hosted behavior.
6. Treat served-model discovery as endpoint observation, not proof of artifact
   digest, weights, runtime, hardware, or model revision beyond the served name.
7. Mark both profiles production-ineligible until Phase 2B evidence and the
   product-owner identity policy approve activation.

## Unresolved before Phase 2B

- Hosted-first versus self-hosted-first decision.
- Authorized credentials and protected-data policy.
- Whether the NVIDIA `/v1/models` response provides stable identity for each
  account/endpoint rather than a catalog-wide listing.
- Exact request/output limits and rate/concurrency limits for the authorized account.
- Tool-call, structured-output, streaming, cancellation, timeout, overload, and
  malformed-response behavior under the selected endpoint.
- Billing usage fields, current price, latency, throughput, quality, and failure rate.
- Acceptable evidence for attributing a hosted response to an exact model artifact.

All unresolved hard constraints remain unknown and fail closed.
