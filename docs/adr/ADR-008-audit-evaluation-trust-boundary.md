# ADR-008: Audit and Evaluation Trust Boundary

- Status: Accepted
- Date: 2026-08-31

## Decision

Audit inspects an output; evaluation chooses what happens next. They remain
separate, versioned, replayable steps. Deterministic checks always run before an
optional model auditor. A model audit is untrusted evidence, never an authority
to execute tools, reveal secrets, alter policy, or exceed a loop bound.

`AuditReport` records generator and auditor deployment/model identities, claims,
evidence requirements, instruction failures, contradictions, uncertainty, and
severity. The evaluation policy emits exactly one of `accept`, `revise`,
`regenerate`, `verify`, `reroute`, or `escalate`. Two iterations is the default
hard bound. High-risk tasks require an independent verification result before
acceptance.

## Threat model

Generated output, retrieved evidence, citations, tool-call arguments, and model
auditor output are attacker-controlled data. Prompt injection may attempt to
override audit instructions, fabricate evidence, exfiltrate secrets, authorize
tool execution, or cause recursive loops. Ryuk therefore uses structured
contracts, deterministic checks, least-privilege adapters, provenance, output
size limits, independent verification, and bounded transitions. The auditor
does not receive deployment credentials and cannot mutate the control plane.

## Measurement gate

Audit policy changes require a versioned labeled corpus reporting action
accuracy and false-accept rate. The initial deterministic corpus requires 100%
action accuracy and zero false accepts. This small fixture validates mechanics,
not real-world model-auditor quality; production model-based audit remains held
until a representative labeled set demonstrates incremental value over the
deterministic baseline.

The approach follows the testing, evaluation, verification, and validation
discipline in the [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf).
