import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.inference.profiles import (
    EvidenceLevel,
    OfflineDeploymentProfile,
    ProfileStatus,
    canonical_profile_json,
    load_offline_deployment_profiles,
)

PROFILE_DIRECTORY = Path("deployments/offline")


def test_phase_2a_profiles_are_unique_frozen_and_production_ineligible() -> None:
    profiles = load_offline_deployment_profiles(PROFILE_DIRECTORY)

    assert len(profiles) == 2
    assert {profile.served_model_name for profile in profiles} == {
        "moonshotai/kimi-k3",
        "deepseek-ai/deepseek-v4-flash-0731",
    }
    assert all(
        profile.status is ProfileStatus.OFFLINE_CANDIDATE for profile in profiles
    )
    assert all(not profile.production_eligible for profile in profiles)
    assert all(profile.runtime_identity is None for profile in profiles)
    assert all(profile.hardware_identity is None for profile in profiles)
    assert all(profile.image_digest is None for profile in profiles)

    with pytest.raises(ValidationError, match="frozen"):
        profiles[0].production_eligible = True


def test_phase_2a_profiles_mark_unverified_hard_evidence_unknown() -> None:
    for profile in load_offline_deployment_profiles(PROFILE_DIRECTORY):
        claims = {claim.name: claim for claim in profile.claims}
        assert claims["artifact_digest"].evidence is EvidenceLevel.UNKNOWN
        assert claims["artifact_digest"].value is None
        assert claims["cancellation"].evidence is EvidenceLevel.UNKNOWN
        assert claims["cancellation"].value is None


def test_profiles_have_stable_canonical_serialization() -> None:
    for path in PROFILE_DIRECTORY.glob("*.json"):
        profile = OfflineDeploymentProfile.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        canonical = canonical_profile_json(profile)
        reparsed = OfflineDeploymentProfile.model_validate_json(canonical)
        assert canonical_profile_json(reparsed) == canonical


def test_offline_profile_rejects_production_activation() -> None:
    document = json.loads(
        (PROFILE_DIRECTORY / "nvidia-hosted-kimi-k3.json").read_text(
            encoding="utf-8"
        )
    )
    document["production_eligible"] = True

    with pytest.raises(ValidationError, match="cannot be production eligible"):
        OfflineDeploymentProfile.model_validate(document)


def test_unknown_claim_rejects_invented_value_or_source() -> None:
    document = json.loads(
        (PROFILE_DIRECTORY / "nvidia-hosted-kimi-k3.json").read_text(
            encoding="utf-8"
        )
    )
    unknown = next(
        claim for claim in document["claims"] if claim["evidence"] == "unknown"
    )
    unknown["value"] = "invented"

    with pytest.raises(ValidationError, match="Unknown claims"):
        OfflineDeploymentProfile.model_validate(document)
