# ADR-017: candidate-specific context preparation and fitting

Date: 2026-09-25. Status: implemented as an offline, explicit preparation
boundary. It is not wired to API dispatch and does not authorize real inputs or
production use.

## Context and decision

Phase 4 requires Ryuk to prepare bounded input for the selected deployment and
to prepare again after model fallback. A shared count or serialized prompt
cannot be assumed valid across candidates. Ryuk owns source selection, trust
metadata, deterministic exclusion, fit decisions and result provenance; a
candidate-bound counter owns tokenizer and chat-template measurement.

The first vertical slice accepts versioned `ContextSegment` sources and one
`ContextPreparationProfile`. The profile binds candidate model/deployment
revision, advertised or verified input capacity and evidence reference, output
reserve, safety margin, counter revision and template revision. The injected counter must match the
profile and count the fully rendered candidate input, including that template's
overhead. External tokenizer and protocol objects do not enter Ryuk contracts.

Only trusted, required policy content may use the system role. Assistant-role
messages must be explicitly marked as assistant history; other non-policy
content is sent with the user role so source/tool/summary text cannot claim
assistant or system authority. Every segment carries a source identifier,
source revision, declared origin/trust class, role, required flag and priority.
These labels do not authorize access or prove a source is accurate. Required
segments are never truncated or removed. Exact, same-role, same-origin optional
duplicates are reduced to their highest-priority copy, retaining an exclusion
record. If the candidate remains over budget, the preparer removes
optional sources by ascending priority and, on ties, later input position first.
It recounts after each removal. If required content still exceeds the available
input window, preparation fails without truncation.

The usable input window is `max_context - reserved_output - safety_margin`.
Count method, confidence, capacity evidence, included and excluded source IDs,
source revisions and a SHA-256 digest of the exact structured message payload
are returned. An estimated count remains labelled as estimated. A fallback must
invoke preparation again with the fallback candidate's own profile and counter;
reusing a previous prepared payload or count is not supported by this contract.

## Scope and safety boundaries

This slice does not implement durable conversations/messages, authorization or
tenant filtering, source retrieval, media preparation, summarization/compaction,
tool/schema overhead, retention/deletion, or a dispatch-time binding check. The
caller is responsible for supplying authorized sources and invoking preparation
again if the candidate, sources, tokenizer, template, generation reserve or
profile changes. Source revisions and payload digests support that future
binding, but do not themselves invalidate a cache or prove source authority.

Offline Phase 2A hosted profiles advertise context capacities but do not
establish exact model tokenizer/template revisions. No first-party exact hosted
tokenizer was available for this offline implementation, and no provider was
contacted. Synthetic test counters demonstrate interface and boundary behavior;
they are not model measurements. Before production dispatch, the selected
counter/template and capacity must have verified evidence and count the exact
payload that will be sent. Estimated counts may not be represented as exact or
as a hard fit guarantee.

## Verification

`tests/test_context_preparation.py` covers exact boundaries, output and safety
reserves, required-content overflow, deterministic priority fitting, exact
duplicate provenance, candidate fallback re-preparation with distinct synthetic
counters, explicit estimated-count metadata, counter/template mismatch, source
identity uniqueness and rejection of untrusted system-role content. Phase 4's
broader exit gate—durable conversation resumption and safe contexts across two
actual candidate deployments—remains open.
