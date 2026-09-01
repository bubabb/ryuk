from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class DataGovernancePolicy:
    classification: DataClassification
    allowed_locations: frozenset[str]
    retention: timedelta
    log_payloads: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_locations or self.retention <= timedelta(0):
            raise ValueError("Governance requires locations and positive retention.")
        if self.classification is DataClassification.RESTRICTED and self.log_payloads:
            raise ValueError("Restricted payloads cannot be logged.")


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    artifact_id: str
    sha256: str
    signature_verified: bool
    scan_passed: bool
    provenance_uri: str

    @property
    def deployable(self) -> bool:
        return self.signature_verified and self.scan_passed and len(self.sha256) == 64


def verify_artifact(path: Path, manifest: ArtifactManifest) -> bool:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest.deployable and digest == manifest.sha256
