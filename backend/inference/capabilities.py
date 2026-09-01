from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from backend.inference.contracts import InferenceTask, TextInput


class EvidenceSource(StrEnum):
    DECLARED = "declared"
    CONFIGURED = "configured"
    DISCOVERED = "discovered"
    MEASURED = "measured"


class TaskKind(StrEnum):
    TEXT = "text"
    CHAT = "chat"


class RejectionReason(StrEnum):
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    MISMATCH = "mismatch"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class CapabilityClaim[T]:
    value: T
    source: EvidenceSource
    scope: str
    runtime_version: str | None = None
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("Capability claim scope must not be blank.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Capability confidence must be between 0 and 1.")
        for timestamp in (self.observed_at, self.expires_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise ValueError(
                    "Capability timestamps must include timezone information."
                )
        if (
            self.observed_at is not None
            and self.expires_at is not None
            and self.expires_at < self.observed_at
        ):
            raise ValueError("Capability expiry cannot precede observation.")


@dataclass(frozen=True, slots=True)
class DeploymentCapabilities:
    task_kinds: CapabilityClaim[frozenset[TaskKind]] | None = None
    served_models: CapabilityClaim[frozenset[str]] | None = None
    max_context_tokens: CapabilityClaim[int] | None = None
    structured_output: CapabilityClaim[bool] | None = None
    streaming: CapabilityClaim[bool] | None = None
    accelerators: CapabilityClaim[frozenset[str]] | None = None
    topologies: CapabilityClaim[frozenset[str]] | None = None
    data_locations: CapabilityClaim[frozenset[str]] | None = None
    production_eligible: CapabilityClaim[bool] | None = None


@dataclass(frozen=True, slots=True)
class ConstraintRejection:
    code: str
    requirement: str
    reason: RejectionReason

    def public_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "requirement": self.requirement,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    rejections: tuple[ConstraintRejection, ...]


def configured_claim[T](
    value: T, scope: str, version: str | None = None
) -> CapabilityClaim[T]:
    return CapabilityClaim(
        value=value,
        source=EvidenceSource.CONFIGURED,
        scope=scope,
        runtime_version=version,
    )


def evaluate_capabilities(
    task: InferenceTask, capabilities: DeploymentCapabilities
) -> EligibilityDecision:
    requirements = task.requirements
    rejections: list[ConstraintRejection] = []
    kind = TaskKind.TEXT if isinstance(task.input, TextInput) else TaskKind.CHAT
    _require_member(rejections, "task_kind", kind, capabilities.task_kinds)
    if requirements.required_model is not None:
        _require_member(
            rejections,
            "served_model",
            requirements.required_model,
            capabilities.served_models,
            mismatch=True,
        )
    if requirements.required_context_tokens is not None:
        context_claim = capabilities.max_context_tokens
        if context_claim is None or not _current(context_claim):
            _unknown(rejections, "context_capacity")
        elif context_claim.value < requirements.required_context_tokens:
            rejections.append(
                ConstraintRejection(
                    "insufficient_context_capacity",
                    "context_capacity",
                    RejectionReason.INSUFFICIENT,
                )
            )
    _require_bool(
        rejections,
        "structured_output",
        requirements.requires_structured_output,
        capabilities.structured_output,
    )
    _require_bool(
        rejections,
        "streaming",
        requirements.requires_streaming,
        capabilities.streaming,
    )
    for name, required, set_claim in (
        ("accelerator", requirements.required_accelerator, capabilities.accelerators),
        ("topology", requirements.required_topology, capabilities.topologies),
        (
            "data_location",
            requirements.required_data_location,
            capabilities.data_locations,
        ),
    ):
        if required is not None:
            _require_member(rejections, name, required, set_claim)
    _require_bool(
        rejections,
        "production_eligible",
        requirements.production_only,
        capabilities.production_eligible,
    )
    return EligibilityDecision(not rejections, tuple(rejections))


def _unknown(rejections: list[ConstraintRejection], requirement: str) -> None:
    rejections.append(
        ConstraintRejection(
            f"unknown_{requirement}", requirement, RejectionReason.UNKNOWN
        )
    )


def _require_member[T](
    rejections: list[ConstraintRejection],
    requirement: str,
    required: T,
    claim: CapabilityClaim[frozenset[T]] | None,
    *,
    mismatch: bool = False,
) -> None:
    if not _current(claim):
        _unknown(rejections, requirement)
    elif claim is not None and required not in claim.value and mismatch:
        rejections.append(
            ConstraintRejection(
                f"mismatched_{requirement}", requirement, RejectionReason.MISMATCH
            )
        )
    elif claim is not None and required not in claim.value:
        rejections.append(
            ConstraintRejection(
                f"unsupported_{requirement}", requirement, RejectionReason.UNSUPPORTED
            )
        )


def _require_bool(
    rejections: list[ConstraintRejection],
    requirement: str,
    required: bool,
    claim: CapabilityClaim[bool] | None,
) -> None:
    if not required:
        return
    if not _current(claim):
        _unknown(rejections, requirement)
    elif claim is not None and not claim.value:
        rejections.append(
            ConstraintRejection(
                f"unsupported_{requirement}", requirement, RejectionReason.UNSUPPORTED
            )
        )


def _current[T](claim: CapabilityClaim[T] | None) -> bool:
    return claim is not None and (
        claim.expires_at is None or claim.expires_at > datetime.now(UTC)
    )
