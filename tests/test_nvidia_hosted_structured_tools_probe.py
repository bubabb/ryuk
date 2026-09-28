import json

import httpx
import pytest

from scripts.probe_nvidia_hosted_failures import (
    APPROVED_MODELS as FAILURE_APPROVED_MODELS,
)
from scripts.probe_nvidia_hosted_structured_tools import (
    APPROVED_MODELS,
    _post_contract,
    collect_structured_tool_evidence,
    sanitize_structured_observation,
    sanitize_tool_observation,
)


def test_probe_model_allowlists_cannot_silently_diverge() -> None:
    assert APPROVED_MODELS == FAILURE_APPROVED_MODELS


def test_structured_observation_validates_schema_without_retaining_content() -> None:
    observation = sanitize_structured_observation(
        model="deepseek-ai/deepseek-v4.1-flash",
        status_code=200,
        elapsed_ms=10,
        payload={
            "id": "private-id",
            "model": "deepseek-ai/deepseek-v4.1-flash",
            "choices": [{"message": {"content": '{"status":"ready"}'}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
        },
    )

    assert observation["contract_valid"] is True
    assert observation["support_decision"] == "supported"
    assert observation["content_characters"] == 18
    assert '{"status":"ready"}' not in str(observation)
    assert "private-id" not in str(observation)


def test_structured_observation_rejects_extra_properties() -> None:
    observation = sanitize_structured_observation(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": "moonshotai/kimi-k3",
            "choices": [{"message": {"content": '{"status":"ready","extra":true}'}}],
        },
    )

    assert observation["json_object_valid"] is True
    assert observation["contract_valid"] is False
    assert observation["support_decision"] == "not_verified"


def test_valid_structured_contract_does_not_override_identity_mismatch() -> None:
    observation = sanitize_structured_observation(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": "different-model",
            "choices": [{"message": {"content": '{"status":"ready"}'}}],
        },
    )

    assert observation["contract_valid"] is True
    assert observation["identity_matches"] is False
    assert observation["support_decision"] == "not_verified"


def test_tool_observation_validates_call_without_retaining_arguments() -> None:
    observation = sanitize_tool_observation(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=10,
        payload={
            "id": "private-id",
            "model": "moonshotai/kimi-k3",
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "private-call-id",
                                "function": {
                                    "name": "lookup_status",
                                    "arguments": '{"item":"ryuk"}',
                                },
                            }
                        ]
                    }
                }
            ],
        },
    )

    assert observation["contract_valid"] is True
    assert observation["tool_executed"] is False
    assert observation["support_decision"] == "supported"
    rendered = str(observation)
    assert "private-id" not in rendered
    assert "private-call-id" not in rendered
    assert '{"item":"ryuk"}' not in rendered


def test_tool_observation_rejects_extra_or_wrong_arguments() -> None:
    observation = sanitize_tool_observation(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=10,
        payload={
            "model": "moonshotai/kimi-k3",
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "lookup_status",
                                    "arguments": '{"item":"other","extra":true}',
                                }
                            }
                        ]
                    }
                }
            ],
        },
    )

    assert observation["arguments_json_valid"] is True
    assert observation["arguments_contract_valid"] is False
    assert observation["contract_valid"] is False
    assert observation["tool_executed"] is False


def test_error_body_is_not_retained() -> None:
    observation = sanitize_tool_observation(
        model="deepseek-ai/deepseek-v4.1-flash",
        status_code=422,
        elapsed_ms=10,
        payload={"error": {"message": "private provider detail"}},
        failure_type="HTTP_422",
    )

    assert observation["error_object_present"] is True
    assert observation["support_decision"] == "not_verified"
    assert "private provider detail" not in str(observation)


@pytest.mark.asyncio
async def test_contract_probe_scopes_reasoning_effort_to_kimi() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        model = requests[-1]["model"]
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"content": '{"status":"ready"}'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await _post_contract(
            client,
            model=APPROVED_MODELS[0],
            kind="structured",
            max_tokens=128,
            temperature=1,
            kimi_reasoning_effort="low",
        )
        await _post_contract(
            client,
            model=APPROVED_MODELS[1],
            kind="structured",
            max_tokens=128,
            temperature=1,
            kimi_reasoning_effort="low",
        )

    assert requests[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in requests[1]


@pytest.mark.asyncio
async def test_probe_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        await collect_structured_tool_evidence("key", max_tokens=0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        await collect_structured_tool_evidence("key", timeout_seconds=0)
    with pytest.raises(ValueError, match="models"):
        await collect_structured_tool_evidence("key", models=())
    with pytest.raises(ValueError, match="approved"):
        await collect_structured_tool_evidence("key", models=("unapproved",))
    with pytest.raises(ValueError, match="temperature"):
        await collect_structured_tool_evidence("key", temperature=-1)
    with pytest.raises(ValueError, match="kimi_reasoning_effort"):
        await collect_structured_tool_evidence("key", kimi_reasoning_effort="medium")
