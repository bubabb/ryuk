import pytest

from scripts.probe_nvidia_hosted_generation import (
    APPROVED_MODELS,
    collect_generation_evidence,
    sanitize_generation_measurement,
)
from scripts.probe_nvidia_hosted_identity import (
    APPROVED_MODELS as IDENTITY_APPROVED_MODELS,
)


def test_probe_model_allowlists_cannot_silently_diverge() -> None:
    assert APPROVED_MODELS == IDENTITY_APPROVED_MODELS


def test_generation_measurement_keeps_counts_but_not_content() -> None:
    payload = {
        "id": "private-request-id",
        "model": "moonshotai/kimi-k3",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "private generated text",
                    "reasoning_content": "private reasoning",
                },
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
    }

    measurement = sanitize_generation_measurement(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=12.3456,
        payload=payload,
    )

    assert measurement["identity_matches"] is True
    assert measurement["output_text_present"] is True
    assert measurement["output_characters"] == len("private generated text")
    assert measurement["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
    }
    rendered = str(measurement)
    assert "private-request-id" not in rendered
    assert "private generated text" not in rendered
    assert "private reasoning" not in rendered


def test_generation_measurement_sanitizes_failure_body() -> None:
    measurement = sanitize_generation_measurement(
        model="deepseek-ai/deepseek-v4.1-flash",
        status_code=400,
        elapsed_ms=10,
        payload={"error": {"message": "account-specific detail"}},
        failure_type="HTTP_400",
    )

    assert measurement["failure_type"] == "HTTP_400"
    assert "account-specific detail" not in str(measurement)


def test_generation_measurement_rejects_invalid_metadata_types() -> None:
    measurement = sanitize_generation_measurement(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": "moonshotai/kimi-k3",
            "choices": [{"finish_reason": {"private": "detail"}}],
            "usage": {"prompt_tokens": -1, "completion_tokens": True},
        },
    )

    assert measurement["finish_reason"] is None
    assert measurement["usage"]["prompt_tokens"] is None
    assert measurement["usage"]["completion_tokens"] is None


@pytest.mark.asyncio
async def test_generation_probe_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        await collect_generation_evidence("key", max_tokens=0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        await collect_generation_evidence("key", timeout_seconds=0)
