# ADR-003: Typed Task and Result Envelope

- **Status:** Accepted for incremental implementation
- **Date:** August 31, 2026
- **Related milestone:** B2

## Context

Ryuk's prototype contract models every request as one prompt plus a caller-owned
model string. That shape cannot represent chat input cleanly and encourages
vendor-specific features to accumulate in an untyped metadata dictionary.

The external FastAPI schema, Ryuk's domain contract, and adapter payloads have
different responsibilities. Treating any one vendor protocol as all three would
weaken Ryuk's independence and make capability enforcement ambiguous.

## Decision

Ryuk will use three contract layers:

1. **API schemas** validate and version external HTTP representations.
2. **Domain types** describe vendor-independent task and result semantics.
3. **Adapter schemas** translate between domain types and one external engine.

The first domain version supports only:

- Plain text input
- Ordered chat messages with `system`, `user`, and `assistant` roles
- Non-streaming text output
- Temperature and maximum output tokens
- Optional requested-model preference
- Request and trace context
- An optional absolute deadline
- Normalized finish reason, token usage, timing, and deployment provenance

Streaming, tools, multimodality, embeddings, reranking, reasoning controls, and
structured output are deliberately excluded from this version. They will be
introduced as explicit typed variants rather than metadata keys.

## Semantic Rules

- Inputs and message contents must be non-empty.
- A chat must contain at least one message.
- Temperature is constrained to the initial portable range `0.0` through `2.0`.
- Maximum output tokens must be positive when supplied.
- Deadlines must be timezone-aware absolute timestamps at API/domain boundaries.
- Execution will later derive a monotonic remaining-time budget from the
  absolute deadline; wall-clock time will not control timeout measurement.
- Missing token counts and timing values mean unknown, not zero.
- Finish reasons use a small Ryuk enum. Adapter-specific reasons are retained in
  namespaced adapter metadata when normalization would lose information.
- A requested model is a routing preference or constraint, never proof of the
  model that executed.
- Result provenance remains authoritative and deployment-derived.

## Metadata Policy

Core semantics must receive typed fields. Metadata is allowed only for:

- Namespaced adapter extensions
- Experimental information not used for correctness or routing
- Diagnostic evidence with a documented retention policy

Routing, identity, deadlines, cancellation, structured output, and usage must
not depend on arbitrary metadata keys.

## Versioning Policy

The domain types evolve through explicit additive changes where semantics remain
compatible. Breaking semantic changes require a new API contract version and a
translation layer during migration.

The current `/inference/generate` endpoint will remain as a compatibility API
during B2. It will translate into the typed domain task. A new versioned API
surface should be introduced before removing or changing existing request
semantics materially.

## Consequences

### Positive

- Chat is modeled without adopting an external provider's schema.
- Unsupported task features can be rejected explicitly.
- Routing requirements become distinguishable from generation parameters.
- Adapters receive a stable semantic contract.
- Audit and evaluation can inspect normalized inputs and results.

### Costs

- Compatibility translation is required for the prototype endpoint.
- Adapters must explicitly support each input variant.
- Streaming and tool support cannot be added as quick metadata flags.

## Rejected Alternatives

### Put all features in `metadata`

Rejected because validation, compatibility filtering, and auditing would depend
on undocumented string keys.

### Adopt an OpenAI request schema internally

Rejected because it would make one external protocol Ryuk's domain model and
would blur semantic differences among engines.

### Design every future modality now

Rejected because it would create speculative abstractions without validated
deployment requirements.

## Migration Sequence

1. Add and test framework-independent contract types.
2. Add API schemas and translation for the existing endpoint.
3. Add engine-adapter translation for text and chat.
4. Return a typed normalized result through the API serializer.
5. Deprecate direct use of the original dataclass contract only after all
   implemented adapters and tests use the new types.
