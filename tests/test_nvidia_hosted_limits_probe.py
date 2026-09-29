import json

import httpx
import pytest

from scripts.probe_nvidia_hosted_limits import (
    MODEL,
    OUTPUT_WORDS,
    _probe_case,
    collect_limit_evidence,
    sanitize_limit_observation,
)


def test_limit_observation_validates_larger_input_without_retaining_content() -> None:
    observation = sanitize_limit_observation(
        case="larger_input",
        status_code=200,
        elapsed_ms=10,
        payload={
            "id": "private-id",
            "model": MODEL,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": "ready",
                        "reasoning_content": "private reasoning",
                    },
                }
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 5},
        },
    )

    assert observation["contract_valid"] is True
    assert observation["identity_matches"] is True
    assert observation["usage"]["prompt_tokens"] == 1000
    rendered = str(observation)
    assert "private-id" not in rendered
    assert "private reasoning" not in rendered


def test_limit_observation_validates_exact_longer_output() -> None:
    content = " ".join(["ready"] * OUTPUT_WORDS)
    observation = sanitize_limit_observation(
        case="longer_output",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": MODEL,
            "choices": [{"message": {"content": content}}],
        },
    )

    assert observation["contract_valid"] is True
    assert observation["output_words"] == OUTPUT_WORDS
    assert content not in str(observation)


def test_limit_observation_rejects_wrong_output_and_identity() -> None:
    observation = sanitize_limit_observation(
        case="longer_output",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": "wrong-model",
            "choices": [{"message": {"content": "ready"}}],
        },
    )

    assert observation["contract_valid"] is False
    assert observation["identity_matches"] is False


@pytest.mark.asyncio
async def test_probe_cases_use_the_preregistered_bounds() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        max_tokens = payload["max_tokens"]
        content = "ready" if max_tokens == 64 else " ".join(["ready"] * OUTPUT_WORDS)
        return httpx.Response(
            200,
            json={"model": MODEL, "choices": [{"message": {"content": content}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        larger = await _probe_case(client, case="larger_input")
        longer = await _probe_case(client, case="longer_output")

    assert [request["max_tokens"] for request in requests] == [64, 256]
    assert len(requests[0]["messages"][0]["content"]) > 6000  # type: ignore[index]
    assert larger["contract_valid"] is True
    assert longer["contract_valid"] is True


@pytest.mark.asyncio
async def test_limit_probe_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        await collect_limit_evidence("key", timeout_seconds=0)
