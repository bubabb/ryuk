# ADR-005: Capability Evidence and Hard Constraints

- **Status:** Accepted
- **Date:** August 31, 2026
- **Related milestone:** D1

## Context

Engine names do not prove that a particular model deployment supports a task.
Eligibility depends on the model, adapter, runtime version, deployment topology,
hardware, and policy boundary. Routing must not infer support from missing data.

## Decision

Ryuk separates caller `RoutingRequirements` from deployment capabilities. The
initial hard requirements cover task kind, required served model, context
capacity, structured output, streaming, accelerator, topology, data location,
and production eligibility. The older `requested_model` remains a soft request;
`required_model` is the hard identity constraint.

Every capability value is a `CapabilityClaim` with evidence source (`declared`,
`configured`, `discovered`, or `measured`), scope, runtime version, observation
and expiry timestamps, and confidence. Missing or expired evidence is `unknown`.
Unknown is distinct from an explicit false value and never satisfies a demanded
feature.

The router evaluates all hard constraints before health probes or scoring. It
emits deterministic structured rejection codes per deployment. A preferred
engine remains a preference: an incompatible preferred deployment may fall back
to another eligible deployment. No score may restore an ineligible candidate.

## Initial Claims

The mock deployment declares text/chat support and explicitly denies streaming,
structured output, and production eligibility. Direct SGLang declares only text
support in this contract version. Model identity and optional context, hardware,
topology, location, and production eligibility come from explicit configuration.
Unconfigured values remain unknown.

Runtime liveness, load, capacity, and freshness collection belong to D2 and are
not capability claims. Capability evidence does not prove current availability.

## Consequences

Eligibility is deterministic and explainable, at the cost of rejecting tasks
when deployment evidence is incomplete. Adding a capability requires a semantic
definition, evidence source, adapter validation, and fixture coverage rather
than a generic engine-level boolean.
