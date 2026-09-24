"""Versioned, payload-free execution history independent of the live registry."""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from backend.inference.contracts import AttemptOutcome, ExecutionAttempt
from backend.inference.deployment import DeploymentRef, ModelRef


def serialize_attempt(attempt: ExecutionAttempt) -> dict[str, Any]:
    result = asdict(attempt)
    result["started_at"] = attempt.started_at.isoformat()
    result["finished_at"] = attempt.finished_at.isoformat()
    result["outcome"] = attempt.outcome.value
    return result


def deserialize_attempt(payload: dict[str, Any]) -> ExecutionAttempt:
    """Read legacy history without inventing missing configured identity."""
    values = dict(payload)
    values["started_at"] = datetime.fromisoformat(values["started_at"])
    values["finished_at"] = datetime.fromisoformat(values["finished_at"])
    values["outcome"] = AttemptOutcome(values["outcome"])
    snapshot = values.get("configured_deployment")
    if snapshot is not None:
        fields = dict(snapshot)
        if fields.get("model") is not None:
            fields["model"] = ModelRef(**fields["model"])
        values["configured_deployment"] = DeploymentRef(**fields)
    return ExecutionAttempt(**values)
