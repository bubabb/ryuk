# ADR-010: hosted identity evidence and activation

Status: accepted for offline work by owner on 2026-09-15. Live activation remains
pending DEC-007; no live call or spend is authorized.

## Evidence semantics

- Configured identity is an operator's claim about a deployment, not an observation.
- Hosted catalog membership is `observed`, never artifact `verified`.
- A missing observation remains configured-only (or unverified when there is no
  configured model). Missing required revision evidence remains configured-only.
- Conflicting observed identifiers produce mismatch.
- Hosted generation responses must carry the exact selected model identifier.
  Missing/invalid response identity is a protocol failure; a different model is
  an identity mismatch. Both follow the existing bounded failover policy.
- Response model names are provider assertions; they do not establish artifact
  digest, model revision, runtime version, hardware, or execution attestation.
- Failed attempts retain only the immutable configured deployment snapshot.
  They do not claim that a failed call executed that model. Successful final
  result provenance carries its separately assessed discovery status.

Attempt schema v2 snapshots deployment, model/revision/served name, engine,
runtime, and opaque endpoint ID. They contain no endpoint URLs, credentials,
prompts, outputs, or provider error bodies. Legacy v1 records remain readable
with absent identity. New snapshots survive registry changes and are included
in the governed API's durable terminal records for success and inference failure.

## Activation boundary

Offline candidates remain production-ineligible. Current production startup
requires VERIFIED identity and therefore rejects catalog-only hosted discovery.
Allowing OBSERVED identity for a bounded hosted certification run or later
production needs an explicit owner decision and a separately implemented gate;
this ADR does not silently weaken startup requirements.

Proposed initial certification policy: synthetic/public inputs only, no private
repository data, exact approved hosted model names, no runtime/revision claims,
explicit budget, and no production activation until live evidence is reviewed.
Owner approved synthetic/public-only offline scope and observed catalog evidence.
No external call is authorized; production/live policy remains pending.

## Research

Checked official references on 2026-09-15:

- https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html
- https://docs.api.nvidia.com/nim/re/reference/llm-apis

The model-listing surface identifies available model names. Treating catalog
membership as weaker evidence than artifact verification is Ryuk's conservative
policy, not a claim that the provider promises artifact attestation. Existing
profile identifiers and external request schemas are unchanged.
