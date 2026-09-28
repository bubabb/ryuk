# NVIDIA Hosted NIM Compatibility Boundary

**Checked:** 2026-09-28
**Status:** Phase 2B in progress; DeepSeek has one bounded generation success,
while Kimi generation and provider-side failure/cancellation contracts remain
uncertified

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

## Bounded live observations

P2B-003 observed one successful DeepSeek V4.1 Flash response at a
41-character synthetic prompt and 64-token output cap. Kimi K3 timed out after
300 seconds. A Kimi-only follow-up using NVIDIA's documented
`reasoning_effort: low`, recommended temperature 1 and a 256-token cap also
timed out after 300 seconds. This is a tested DeepSeek lower bound, not a
maximum-limit claim, and the Kimi observations are not proof of unavailability.

P2B-004 observed both exact routes timing out after 30 seconds on an
intentionally malformed `messages` value rather than returning an HTTP
validation response. Separate streaming requests were closed by the client at
two seconds before response headers. The provider exposed no cancellation
acknowledgment or late-result channel, so execution termination remains unknown.
No overload was deliberately induced. See the dated reports and sanitized JSON
records under `docs/reports/` and `evidence/phase2b/`.

P2B-005 verified one DeepSeek V4.1 Flash tool proposal: the provider returned
the exact model ID and one requested function call with schema-valid arguments.
Ryuk validated the proposal as data and did not execute it. DeepSeek structured
output returned HTTP 200 but no content at the tested 128-token cap, so the
structured contract remains unverified. Both Kimi structured/tool requests
timed out at 180 seconds. These observations do not yet authorize enabling
structured output or tool calls in the deployment registry.

A DeepSeek-only follow-up omitted `response_format` and required exact JSON by
prompt plus deterministic validation. It returned the exact
`{"status":"ready"}` object with matching model identity and usage. This
verifies a prompt-constrained JSON fallback at the tested point, not
provider-enforced structured output. The earlier `response_format` request
remains unverified because its HTTP 200 response contained no answer content.

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
