import pytest

from scripts.probe_nvidia_hosted_failures import (
    APPROVED_MODELS,
    collect_failure_evidence,
    sanitize_error_shape,
)
from scripts.probe_nvidia_hosted_generation import (
    APPROVED_MODELS as GENERATION_APPROVED_MODELS,
)


def test_probe_model_allowlists_cannot_silently_diverge() -> None:
    assert APPROVED_MODELS == GENERATION_APPROVED_MODELS


def test_error_shape_excludes_provider_message_and_extra_fields() -> None:
    shape = sanitize_error_shape(
        {
            "error": {
                "type": "invalid_request",
                "code": 422,
                "message": "account-specific private detail",
                "request_id": "private-request-id",
            }
        }
    )

    assert shape == {
        "error_object_present": True,
        "error_type_present": True,
        "error_code_present": True,
    }
    rendered = str(shape)
    assert "account-specific private detail" not in rendered
    assert "private-request-id" not in rendered


def test_error_shape_rejects_nested_or_boolean_code() -> None:
    shape = sanitize_error_shape(
        {"error": {"type": {"private": "detail"}, "code": True}}
    )

    assert shape["error_type_present"] is False
    assert shape["error_code_present"] is False


@pytest.mark.asyncio
async def test_failure_probe_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="cancellation_seconds"):
        await collect_failure_evidence("key", cancellation_seconds=0)
    with pytest.raises(ValueError, match="must exceed"):
        await collect_failure_evidence(
            "key", cancellation_seconds=2, request_timeout_seconds=2
        )
