# NVIDIA Hosted NIM Compatibility Boundary

**Checked:** 2026-09-09
**Status:** Phase 2A offline contract implementation; not externally certified

`NVIDIAHostedNIMEngine` contains NVIDIA API Catalog chat-completion details at
the adapter boundary. Ryuk's typed task, result, reasoning, usage, failure, and
provenance contracts remain authoritative.

## Pinned profiles

| Model | Request reasoning translation | Response reasoning fields |
| --- | --- | --- |
| `moonshotai/kimi-k3` | top-level `reasoning_effort` | `message.reasoning_content`, with `message.reasoning` accepted as a documented compatibility fallback |
| `deepseek-ai/deepseek-v4-flash-0731` | `chat_template_kwargs.thinking=true` plus nested `reasoning_effort` | `message.reasoning` or `message.reasoning_content` |

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
- Kimi image input and preserved reasoning/tool history on subsequent turns.
- Exact context/output/rate limits for an authorized account.
- Artifact digest, hosted runtime, hardware, and stronger identity evidence.

These remain separate vertical slices or Phase 2B evidence. Advertised support
does not make a hard capability eligible.

## Offline evidence

The sanitized Phase 2A fixtures exercise exact request shapes, both reasoning
response spellings, identity discovery, answer/reasoning separation, usage,
overload, timeout, malformed output, and response-size enforcement. Real hosted
behavior remains gated by `NVIDIA_API_KEY` and the product-owner decisions in
`docs/ACTION_ITEMS.md`.
