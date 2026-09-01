from datetime import UTC, datetime

import pytest

from backend.inference.deployment import (
    DeploymentRef,
    IdentityAssessment,
    IdentityVerification,
    ModelIdentityObservation,
    ModelRef,
    assess_model_identity,
)


def observation(model: ModelRef) -> ModelIdentityObservation:
    return ModelIdentityObservation(
        model=model,
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        source="sglang:/model_info",
    )


def test_deployment_ref_keeps_model_engine_and_runtime_separate() -> None:
    deployment = DeploymentRef(
        deployment_id="sglang-kimi-primary",
        model=ModelRef(
            artifact_id="moonshotai/Kimi-K2",
            revision="sha256:abc",
            served_name="kimi-k2",
        ),
        engine_name="sglang",
        engine_version="0.5.18",
        serving_runtime="standalone",
        endpoint_id="gpu-worker-1",
    )

    assert deployment.model is not None
    assert deployment.model.artifact_id == "moonshotai/Kimi-K2"
    assert deployment.engine_name == "sglang"
    assert deployment.serving_runtime == "standalone"


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("artifact_id", {"artifact_id": ""}),
        ("artifact_id", {"artifact_id": " model"}),
        ("revision", {"artifact_id": "model", "revision": ""}),
        ("served_name", {"artifact_id": "model", "served_name": "name "}),
    ],
)
def test_model_ref_rejects_invalid_identifiers(field_name, kwargs) -> None:
    with pytest.raises(ValueError, match=field_name):
        ModelRef(**kwargs)


def test_observation_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        ModelIdentityObservation(
            model=ModelRef(artifact_id="model"),
            observed_at=datetime(2026, 8, 31),
            source="discovery",
        )


def test_matching_complete_identity_is_verified() -> None:
    expected = ModelRef("model", revision="rev-1", served_name="served")

    assessment = assess_model_identity(expected, observation(expected))

    assert assessment.status is IdentityVerification.VERIFIED
    assert assessment.mismatched_fields == ()


def test_missing_observed_field_is_not_treated_as_verified() -> None:
    expected = ModelRef("model", revision="rev-1", served_name="served")
    observed = observation(ModelRef("model", served_name="served"))

    assessment = assess_model_identity(expected, observed)

    assert assessment.status is IdentityVerification.CONFIGURED_ONLY


def test_conflicting_fields_are_reported() -> None:
    expected = ModelRef("model-a", revision="rev-1", served_name="served-a")
    observed = observation(
        ModelRef("model-b", revision="rev-1", served_name="served-b")
    )

    assessment = assess_model_identity(expected, observed)

    assert assessment.status is IdentityVerification.MISMATCH
    assert assessment.mismatched_fields == ("artifact_id", "served_name")


def test_configured_identity_without_observation_is_configured_only() -> None:
    assessment = assess_model_identity(ModelRef("model"), None)

    assert assessment.status is IdentityVerification.CONFIGURED_ONLY


def test_observation_without_expected_identity_is_unverified() -> None:
    observed = observation(ModelRef("model"))

    assessment = assess_model_identity(None, observed)

    assert assessment.status is IdentityVerification.UNVERIFIED


def test_mismatch_assessment_requires_conflicting_fields() -> None:
    with pytest.raises(ValueError, match="must identify"):
        IdentityAssessment(
            status=IdentityVerification.MISMATCH,
            expected=ModelRef("expected"),
            observed=observation(ModelRef("observed")),
        )
