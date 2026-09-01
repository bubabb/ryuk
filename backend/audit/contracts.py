from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AuditSeverity(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class FindingKind(StrEnum):
    SCHEMA = "schema"
    REQUIRED_SECTION = "required_section"
    CITATION = "citation"
    LENGTH = "length"
    LANGUAGE = "language"
    POLICY = "policy"
    SECRET = "secret"
    CLAIM = "claim"
    CONTRADICTION = "contradiction"
    INSTRUCTION = "instruction"
    PROMPT_INJECTION = "prompt_injection"


@dataclass(frozen=True, slots=True)
class AuditIdentity:
    deployment_id: str
    model_artifact_id: str
    model_revision: str | None

    def __post_init__(self) -> None:
        if not self.deployment_id.strip() or not self.model_artifact_id.strip():
            raise ValueError("Audit identities must not be blank.")


@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    claim: str
    evidence_required: bool
    supported: bool | None
    uncertainty: float

    def __post_init__(self) -> None:
        if not self.claim.strip() or not 0 <= self.uncertainty <= 1:
            raise ValueError("Claim assessment is invalid.")


@dataclass(frozen=True, slots=True)
class AuditFinding:
    kind: FindingKind
    severity: AuditSeverity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AuditReport:
    report_version: str
    generator: AuditIdentity
    auditor: AuditIdentity | None
    deterministic_findings: tuple[AuditFinding, ...]
    claims: tuple[ClaimAssessment, ...] = ()
    instruction_failures: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    uncertainty: float = 0.0

    def __post_init__(self) -> None:
        if not self.report_version.strip() or not 0 <= self.uncertainty <= 1:
            raise ValueError("Audit report version or uncertainty is invalid.")

    @property
    def maximum_severity(self) -> AuditSeverity:
        severities = [item.severity for item in self.deterministic_findings]
        if self.instruction_failures or self.contradictions:
            severities.append(AuditSeverity.ERROR)
        return max(severities, default=AuditSeverity.INFO)
