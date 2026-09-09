from __future__ import annotations

import hashlib
import re
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
    sbom_uri: str
    attestation_verified: bool
    image_digest: str

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("Artifact identifiers must not be blank.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Artifact SHA-256 must be 64 lowercase hex characters.")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_digest):
            raise ValueError("Container images must use immutable SHA-256 digests.")
        if not self.provenance_uri.startswith("https://"):
            raise ValueError("Artifact provenance requires an HTTPS URI.")
        if not self.sbom_uri.startswith("https://"):
            raise ValueError("Artifact SBOM requires an HTTPS URI.")

    @property
    def deployable(self) -> bool:
        return (
            self.signature_verified
            and self.attestation_verified
            and self.scan_passed
        )


def verify_artifact(path: Path, manifest: ArtifactManifest) -> bool:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest.deployable and digest == manifest.sha256
