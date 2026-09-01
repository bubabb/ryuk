from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from backend.inference.errors import UpstreamProtocolFailure


def _require_identifier(value: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty without outer whitespace.")


def _validate_optional_identifier(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_identifier(value, field_name)


class IdentityVerification(StrEnum):
    VERIFIED = "verified"
    CONFIGURED_ONLY = "configured_only"
    UNVERIFIED = "unverified"
    MISMATCH = "mismatch"


class IdentityDiscoveryFailure(UpstreamProtocolFailure):
    """An external deployment identity could not be discovered safely."""


@dataclass(frozen=True, slots=True)
class ModelRef:
    """Ryuk's configured or observed identity for one model artifact."""

    artifact_id: str
    revision: str | None = None
    served_name: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.artifact_id, "artifact_id")
        _validate_optional_identifier(self.revision, "revision")
        _validate_optional_identifier(self.served_name, "served_name")


@dataclass(frozen=True, slots=True)
class DeploymentRef:
    """Stable identity for an executable model deployment."""

    deployment_id: str
    model: ModelRef | None
    engine_name: str
    endpoint_id: str
    engine_version: str | None = None
    serving_runtime: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.deployment_id, "deployment_id")
        _require_identifier(self.engine_name, "engine_name")
        _require_identifier(self.endpoint_id, "endpoint_id")
        _validate_optional_identifier(self.engine_version, "engine_version")
        _validate_optional_identifier(self.serving_runtime, "serving_runtime")


@dataclass(frozen=True, slots=True)
class ModelIdentityObservation:
    """Model identity discovered from an external deployment boundary."""

    model: ModelRef
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        _require_identifier(self.source, "source")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include timezone information.")


@dataclass(frozen=True, slots=True)
class IdentityDiscovery:
    observation: ModelIdentityObservation
    adapter_metadata: dict[str, Any]


@runtime_checkable
class IdentityDiscoveringEngine(Protocol):
    async def discover_model_identity(self) -> IdentityDiscovery: ...


@dataclass(frozen=True, slots=True)
class IdentityAssessment:
    status: IdentityVerification
    expected: ModelRef | None
    observed: ModelIdentityObservation | None
    mismatched_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status is IdentityVerification.MISMATCH and not self.mismatched_fields:
            raise ValueError("A mismatch assessment must identify conflicting fields.")
        if self.status is not IdentityVerification.MISMATCH and self.mismatched_fields:
            raise ValueError(
                "Only a mismatch assessment may contain conflicting fields."
            )


@dataclass(frozen=True, slots=True)
class IdentityInspection:
    assessment: IdentityAssessment
    discovery_error: str | None = None


def assess_model_identity(
    expected: ModelRef | None,
    observed: ModelIdentityObservation | None,
) -> IdentityAssessment:
    """Compare identity evidence without inventing equivalence or verification."""

    if expected is None:
        return IdentityAssessment(
            status=IdentityVerification.UNVERIFIED,
            expected=None,
            observed=observed,
        )

    if observed is None:
        return IdentityAssessment(
            status=IdentityVerification.CONFIGURED_ONLY,
            expected=expected,
            observed=None,
        )

    mismatches: list[str] = []
    missing_evidence = False
    for field_name in ("artifact_id", "revision", "served_name"):
        expected_value = getattr(expected, field_name)
        if expected_value is None:
            continue

        observed_value = getattr(observed.model, field_name)
        if observed_value is None:
            missing_evidence = True
        elif observed_value != expected_value:
            mismatches.append(field_name)

    if mismatches:
        return IdentityAssessment(
            status=IdentityVerification.MISMATCH,
            expected=expected,
            observed=observed,
            mismatched_fields=tuple(mismatches),
        )

    status = (
        IdentityVerification.CONFIGURED_ONLY
        if missing_evidence
        else IdentityVerification.VERIFIED
    )
    return IdentityAssessment(status=status, expected=expected, observed=observed)
