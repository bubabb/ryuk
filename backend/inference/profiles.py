from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ProfileStatus(StrEnum):
    OFFLINE_CANDIDATE = "offline_candidate"
    CERTIFIED = "certified"
    REJECTED = "rejected"


class DeploymentMode(StrEnum):
    HOSTED = "hosted"
    SELF_HOSTED = "self_hosted"


class EvidenceLevel(StrEnum):
    ADVERTISED = "advertised"
    CONTRACT_TESTED = "contract_tested"
    OBSERVED = "observed"
    VERIFIED = "verified"
    UNKNOWN = "unknown"


class ProfileClaim(BaseModel):
    """One immutable profile value and the evidence supporting it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: str | int | float | bool | None
    evidence: EvidenceLevel
    source: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> ProfileClaim:
        if self.evidence is EvidenceLevel.UNKNOWN:
            if self.value is not None or self.source is not None:
                raise ValueError("Unknown claims cannot carry a value or source.")
        elif self.value is None or self.source is None:
            raise ValueError("Known claims require both a value and source.")
        return self


class OfflineDeploymentProfile(BaseModel):
    """Validated Phase 2A evidence, not an executable deployment registration."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1]
    profile_id: str = Field(min_length=1)
    status: ProfileStatus
    provider: str = Field(min_length=1)
    deployment_mode: DeploymentMode
    base_url: HttpUrl
    generation_path: str = Field(pattern=r"^/")
    adapter_name: str = Field(min_length=1)
    model_artifact_id: str = Field(min_length=1)
    model_revision: str | None = None
    served_model_name: str = Field(min_length=1)
    runtime_identity: str | None = None
    hardware_identity: str | None = None
    image_digest: str | None = None
    production_eligible: bool
    contract_checked_on: date
    sources: tuple[HttpUrl, ...] = Field(min_length=1)
    claims: tuple[ProfileClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_offline_profile(self) -> OfflineDeploymentProfile:
        if self.status is not ProfileStatus.OFFLINE_CANDIDATE:
            raise ValueError("Offline profiles must remain offline candidates.")
        if self.production_eligible:
            raise ValueError("Offline profiles cannot be production eligible.")
        if self.deployment_mode is DeploymentMode.HOSTED and any(
            value is not None
            for value in (
                self.runtime_identity,
                self.hardware_identity,
                self.image_digest,
            )
        ):
            raise ValueError(
                "Hosted offline profiles cannot invent runtime, hardware, "
                "or image identity."
            )
        if self.model_revision is not None and (
            not self.model_revision.strip()
            or self.model_revision != self.model_revision.strip()
        ):
            raise ValueError("Model revision must be absent or a clean identifier.")
        claim_names = tuple(claim.name for claim in self.claims)
        if len(set(claim_names)) != len(claim_names):
            raise ValueError("Profile claim names must be unique.")
        if len(set(map(str, self.sources))) != len(self.sources):
            raise ValueError("Profile sources must be unique.")
        return self


def load_offline_deployment_profile(path: Path) -> OfflineDeploymentProfile:
    """Load and validate a checked-in profile without activating its endpoint."""
    content = path.read_text(encoding="utf-8")
    return OfflineDeploymentProfile.model_validate_json(content)


def load_offline_deployment_profiles(
    directory: Path,
) -> tuple[OfflineDeploymentProfile, ...]:
    profiles = tuple(
        load_offline_deployment_profile(path)
        for path in sorted(directory.glob("*.json"))
    )
    profile_ids = tuple(profile.profile_id for profile in profiles)
    if len(set(profile_ids)) != len(profile_ids):
        raise ValueError("Deployment profile identifiers must be unique.")
    model_names = tuple(profile.served_model_name for profile in profiles)
    if len(set(model_names)) != len(model_names):
        raise ValueError("Offline served-model names must be unique.")
    return profiles


def canonical_profile_json(profile: OfflineDeploymentProfile) -> str:
    """Return stable profile content for review, hashing, and change detection."""
    payload = profile.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
