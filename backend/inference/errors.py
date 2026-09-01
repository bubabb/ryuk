from enum import StrEnum
from typing import Any


class RetryClassification(StrEnum):
    NEVER = "never"
    SAME_DEPLOYMENT = "same_deployment"
    OTHER_DEPLOYMENT = "other_deployment"


class InferenceFailure(Exception):
    code = "inference_failure"
    public_message = "Inference failed."
    http_status = 500
    retry = RetryClassification.NEVER

    def __init__(
        self,
        *,
        deployment_id: str | None = None,
        attempt_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(self.public_message)
        self.deployment_id = deployment_id
        self.attempt_id = attempt_id
        self.context = context or {}

    @property
    def retryable(self) -> bool:
        return self.retry is not RetryClassification.NEVER

    def public_payload(self, request_id: str) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.public_message,
            "retryable": self.retryable,
            "request_id": request_id,
        }


class ConfigurationFailure(InferenceFailure):
    code = "configuration_failure"
    public_message = "Inference service configuration is invalid."
    http_status = 500


class IdentityMismatchFailure(InferenceFailure):
    code = "identity_mismatch"
    public_message = "The deployment model identity does not match configuration."
    http_status = 503
    retry = RetryClassification.OTHER_DEPLOYMENT


class DeploymentUnavailableFailure(InferenceFailure):
    code = "deployment_unavailable"
    public_message = "No inference deployment is currently available."
    http_status = 503
    retry = RetryClassification.OTHER_DEPLOYMENT


class UnsupportedTaskFailure(InferenceFailure):
    code = "unsupported_task"
    public_message = "The selected deployment does not support this task."
    http_status = 422


class CapabilityMismatchFailure(InferenceFailure):
    code = "capability_mismatch"
    public_message = "No deployment satisfies the task requirements."
    http_status = 422

    def public_payload(self, request_id: str) -> dict[str, object]:
        payload = super().public_payload(request_id)
        rejections = self.context.get("rejections")
        if isinstance(rejections, list):
            payload["rejections"] = rejections
        return payload


class CapacityExceededFailure(InferenceFailure):
    code = "capacity_exceeded"
    public_message = "The inference deployment has no available capacity."
    http_status = 503
    retry = RetryClassification.OTHER_DEPLOYMENT


class DeadlineExceededFailure(InferenceFailure):
    code = "deadline_exceeded"
    public_message = "The inference deadline was exceeded."
    http_status = 504
    retry = RetryClassification.OTHER_DEPLOYMENT


class UpstreamProtocolFailure(InferenceFailure):
    code = "upstream_protocol_failure"
    public_message = "The inference deployment returned an invalid response."
    http_status = 502
    retry = RetryClassification.OTHER_DEPLOYMENT


class GenerationFailure(InferenceFailure):
    code = "generation_failure"
    public_message = "The inference deployment failed to generate a result."
    http_status = 502
    retry = RetryClassification.OTHER_DEPLOYMENT


class CancelledFailure(InferenceFailure):
    code = "cancelled"
    public_message = "Inference was cancelled."
    http_status = 499


class UnknownEnginePreferenceFailure(InferenceFailure):
    code = "unknown_engine_preference"
    public_message = "The requested inference engine is not registered."
    http_status = 400
