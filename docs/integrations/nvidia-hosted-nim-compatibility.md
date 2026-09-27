# NVIDIA Hosted NIM Compatibility Boundary

**Checked:** 2026-09-26
**Status:** Phase 2A offline contracts plus P2B-001 authenticated catalog inventory; generation not externally certified

`NVIDIAHostedNIMEngine` contains NVIDIA API Catalog chat-completion details at
the adapter boundary. Ryuk's typed task, result, reasoning, usage, failure, and
provenance contracts remain authoritative.

## Pinned profiles

| Model | Request reasoning translation | Response reasoning fields |
| --- | --- | --- |
| `moonshotai/kimi-k3` | top-level `reasoning_effort` | `message.reasoning_content`, with `message.reasoning` accepted as a documented compatibility fallback |
| `deepseek-ai/deepseek-v4.1-flash` | none until the hosted API's numeric reasoning mapping is contract-tested | `message.reasoning` or `message.reasoning_content` |

The deprecated `deepseek-ai/deepseek-v4-flash-0731` translation remains in the
adapter only for historical replay compatibility; its profile and fixture are
retained under the historical evidence directories and are not active
candidates.

The adapter rejects moving or unknown model aliases. Adding another hosted
model requires a deliberate profile and contract change.

Provider-returned reasoning is normalized into a separate Ryuk
`ReasoningOutput` and carried through the router. It is not concatenated with
the answer, stored in adapter metadata, or exposed by the current public API.
Any future reasoning disclosure requires an explicit policy and API contract.

Malformed reasoning types fail as a sanitized `UpstreamProtocolFailure`.
Provider error bodies, reasoning text, credentials, and response headers do not
enter public failure messages.

## Deliberately unsupported or unverified

- Direct text-completion calls on the hosted profiles.
- Streaming and disconnected-client cancellation.
- Structured output and tool-call translation.
- Kimi image input, DeepSeek V4.1 image input, and preserved reasoning/tool
  history on subsequent turns.
- DeepSeek V4.1 numeric reasoning-effort translation; the model documentation
  describes values from 1 to 100, but the published hosted request schema does
  not expose the field.
- Exact context/output/rate limits for an authorized account.
- Artifact digest, hosted runtime, hardware, and stronger identity evidence.

These remain separate vertical slices or Phase 2B evidence. Advertised support
does not make a hard capability eligible.

## Authenticated catalog inventory

P2B-001 observed both exact approved model IDs through an authenticated,
read-only `GET /v1/models` request to the shared hosted API origin. This proves
account-visible catalog access, not generation readiness, served response
identity, model-weight identity, runtime identity, or separate physical
deployments. See
`docs/reports/P2B-001-authorized-endpoint-inventory-2026-09-26.md`.

## Offline evidence

The sanitized Phase 2A fixtures exercise exact request shapes, both reasoning
response spellings, identity discovery, answer/reasoning separation, usage,
overload, timeout, malformed output, and response-size enforcement. Real hosted
generation behavior remains gated by the controlled P2B-002 through P2B-005
checks and the product-owner decisions in `docs/ACTION_ITEMS.md`.

## Identity hardening (2026-09-15)

Hosted catalog matches are OBSERVED, not VERIFIED. Missing required revision
evidence remains CONFIGURED_ONLY. Generation responses must name the exact
selected model; missing model identity is a protocol failure and a different
model is an identity mismatch. Both use bounded router failure handling.
Production startup still requires VERIFIED identity. See ADR-010 for evidence
semantics, official references, and the pending hosted activation decision.
