import pytest

from backend.inference.errors import (
    CancelledFailure,
    CapabilityMismatchFailure,
    CapacityExceededFailure,
    ConfigurationFailure,
    DeadlineExceededFailure,
    DeploymentUnavailableFailure,
    GenerationFailure,
    IdentityMismatchFailure,
    InferenceFailure,
    RetryClassification,
    UnknownEnginePreferenceFailure,
    UnsupportedTaskFailure,
    UpstreamProtocolFailure,
)


@pytest.mark.parametrize(
    ("failure_type", "code", "status", "retry"),
    [
        (InferenceFailure, "inference_failure", 500, RetryClassification.NEVER),
        (ConfigurationFailure, "configuration_failure", 500, RetryClassification.NEVER),
        (
            IdentityMismatchFailure,
            "identity_mismatch",
            503,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (
            DeploymentUnavailableFailure,
            "deployment_unavailable",
            503,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (UnsupportedTaskFailure, "unsupported_task", 422, RetryClassification.NEVER),
        (
            CapacityExceededFailure,
            "capacity_exceeded",
            503,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (
            DeadlineExceededFailure,
            "deadline_exceeded",
            504,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (
            UpstreamProtocolFailure,
            "upstream_protocol_failure",
            502,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (
            GenerationFailure,
            "generation_failure",
            502,
            RetryClassification.OTHER_DEPLOYMENT,
        ),
        (CancelledFailure, "cancelled", 499, RetryClassification.NEVER),
        (
            CapabilityMismatchFailure,
            "capability_mismatch",
            422,
            RetryClassification.NEVER,
        ),
        (
            UnknownEnginePreferenceFailure,
            "unknown_engine_preference",
            400,
            RetryClassification.NEVER,
        ),
    ],
)
def test_failure_taxonomy_has_stable_policy(
    failure_type: type[InferenceFailure],
    code: str,
    status: int,
    retry: RetryClassification,
) -> None:
    failure = failure_type()

    assert failure.code == code
    assert failure.http_status == status
    assert failure.retry is retry
    assert failure.retryable is (retry is not RetryClassification.NEVER)


def test_public_payload_excludes_internal_diagnostics() -> None:
    failure = GenerationFailure(
        deployment_id="deployment-secret",
        attempt_id="attempt-secret",
        context={"upstream_body": "credential-secret"},
    )

    payload = failure.public_payload("request-public")

    assert payload == {
        "code": "generation_failure",
        "message": "The inference deployment failed to generate a result.",
        "retryable": True,
        "request_id": "request-public",
    }
    assert "secret" not in str(failure)


def test_wrapped_failure_retains_original_cause_without_exposing_it() -> None:
    original = RuntimeError("credential-secret")

    try:
        raise DeploymentUnavailableFailure(
            context={"operation": "generation"}
        ) from original
    except DeploymentUnavailableFailure as failure:
        assert failure.__cause__ is original
        assert "credential-secret" not in str(failure)
