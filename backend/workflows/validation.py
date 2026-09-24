"""Artifact-bound deterministic acceptance using Ryuk's existing audit rules."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from typing import Any

from backend.audit.deterministic import ValidationPolicy, validate_output
from backend.inference.advanced import JSONSchemaConstraint
from backend.workflows.contracts import StoredArtifact, canonical_json

VALIDATOR_VERSION = "workflow-deterministic-v1"


def policy_snapshot(policy: ValidationPolicy) -> dict[str, Any]:
    """Detach mutable schemas and reject rules this validator cannot enforce."""
    if not isinstance(policy, ValidationPolicy):
        raise ValueError("A ValidationPolicy is required")
    if (
        type(policy.minimum_chars) is not int
        or type(policy.maximum_chars) is not int
        or type(policy.require_citations) is not bool
        or policy.language not in (None, "ascii")
    ):
        raise ValueError("Unsupported validation policy")
    for values in (policy.required_sections, policy.forbidden_phrases):
        if not isinstance(values, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise ValueError("Validation rules must be nonempty strings")
    snapshot: dict[str, Any] = json.loads(canonical_json(asdict(policy)))
    schema = snapshot["output_schema"]
    if schema is not None:
        schema = schema["schema"]
        JSONSchemaConstraint(schema)
        if set(schema) - {"type", "properties", "required", "additionalProperties"}:
            raise ValueError("Unsupported schema keyword")
        if (
            "additionalProperties" in schema
            and type(schema["additionalProperties"]) is not bool
        ):
            raise ValueError("additionalProperties must be boolean")
        for rule in schema["properties"].values():
            if (
                not isinstance(rule, dict)
                or set(rule) != {"type"}
                or rule["type"]
                not in ("string", "integer", "number", "boolean", "array", "object")
            ):
                raise ValueError("Unsupported schema property rule")
    return snapshot


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite JSON number")
    return number


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON value")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def validate_artifact(
    artifact: StoredArtifact, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate saved output; any finding rejects this deterministic gate."""
    rules = dict(snapshot)
    rules["required_sections"] = tuple(rules["required_sections"])
    rules["forbidden_phrases"] = tuple(rules["forbidden_phrases"])
    schema = rules["output_schema"]
    rules["output_schema"] = JSONSchemaConstraint(schema["schema"]) if schema else None
    policy = ValidationPolicy(**rules)
    output = artifact.payload().get("output")
    text = output.get("text") if isinstance(output, dict) else None
    findings: list[dict[str, str]] = []
    if not isinstance(text, str) or not text.strip():
        findings.append({"kind": "schema", "code": "missing_output_text"})
    else:
        if schema is not None:
            try:
                json.loads(
                    text,
                    parse_constant=_reject_constant,
                    parse_float=_finite_float,
                    object_pairs_hook=_unique_object,
                )
            except (ValueError, RecursionError):
                findings.append({"kind": "schema", "code": "invalid_json"})
        if not findings:
            findings.extend(
                # Do not copy dynamic field names, rule strings or output into reports.
                {
                    "kind": finding.kind.value,
                    "code": finding.kind.value + "_rule_failed",
                }
                for finding in validate_output(text, policy)
            )
    return {
        "schema_version": 1,
        "validator_version": VALIDATOR_VERSION,
        "workflow_id": artifact.ref.workflow_id,
        "artifact": {
            "artifact_id": artifact.ref.artifact_id,
            "sha256": artifact.ref.sha256,
        },
        "policy": snapshot,
        "decision": "rejected" if findings else "accepted",
        "findings": findings,
    }
