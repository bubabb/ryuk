import json

import httpx
import pytest

from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    FinishReason,
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.engines.dynamo import DynamoEngine
from backend.inference.engines.nim import NIMEngine
from backend.inference.errors import CapacityExceededFailure, UpstreamProtocolFailure


def task(value: TextInput | ChatInput) -> InferenceTask:
    return InferenceTask(
        input=value,
        generation=GenerationConfig(max_output_tokens=8, temperature=0.2),
        requirements=TaskRequirements(),
        trace=TraceContext("request-managed-1"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "kwargs", "health_path"),
    [
        (
            DynamoEngine,
            {"topology": "aggregated", "runtime_version": "1.4.1"},
            "/health",
        ),
        (
            NIMEngine,
            {"expected_release": "2.0.11", "profile_id": "profile-a"},
            "/v1/health/ready",
        ),
    ],
)
async def test_managed_adapter_health_and_text_contract(
    adapter_type, kwargs, health_path
) -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == health_path:
            return httpx.Response(200)
        captured.update(json.loads(request.content))
        assert request.headers["x-request-id"] == "request-managed-1"
        return httpx.Response(
            200,
            json={
                "id": "response-1",
                "model": "model-a",
                "choices": [{"text": "done", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )

    adapter = adapter_type(
        "http://managed",
        model="model-a",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        **kwargs,
    )
    assert await adapter.is_available()
    result = await adapter.generate_task(task(TextInput("hello")))
    assert captured["prompt"] == "hello"
    assert captured["stream"] is False
    assert result.output.text == "done"
    assert result.finish_reason is FinishReason.STOP


@pytest.mark.asyncio
async def test_chat_protocol_is_contained_inside_nim_adapter() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello"}}], "usage": {}},
        )

    adapter = NIMEngine(
        "http://nim",
        model="model-a",
        expected_release="2.0.11",
        profile_id="profile-a",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await adapter.generate_task(task(ChatInput((ChatMessage(ChatRole.USER, "hi"),))))
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_nim_discovers_and_verifies_release_profile_and_model() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payloads = {
            "/v1/models": {"data": [{"id": "model-a"}]},
            "/v1/version": {"version": "2.0.11"},
            "/v1/metadata": {"profile_id": "profile-a", "backend": "vllm"},
        }
        return httpx.Response(200, json=payloads[request.url.path])

    adapter = NIMEngine(
        "http://nim",
        model="model-a",
        expected_release="2.0.11",
        profile_id="profile-a",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    identity = await adapter.discover_model_identity()
    assert identity.observation.model.artifact_id == "model-a"
    assert identity.adapter_metadata["nim"] == {
        "release": "2.0.11",
        "profile_id": "profile-a",
        "backend": "vllm",
    }


@pytest.mark.asyncio
async def test_nim_rejects_profile_mismatch_and_safe_capacity_failure() -> None:
    async def mismatch(request: httpx.Request) -> httpx.Response:
        payloads = {
            "/v1/models": {"data": [{"id": "model-a"}]},
            "/v1/version": {"version": "2.0.11"},
            "/v1/metadata": {"profile_id": "wrong"},
        }
        return httpx.Response(200, json=payloads[request.url.path])

    adapter = NIMEngine(
        "http://nim",
        model="model-a",
        expected_release="2.0.11",
        profile_id="profile-a",
        client=httpx.AsyncClient(transport=httpx.MockTransport(mismatch)),
    )
    with pytest.raises(UpstreamProtocolFailure):
        await adapter.discover_model_identity()

    async def overloaded(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="secret upstream body")

    adapter = NIMEngine(
        "http://nim",
        model="model-a",
        expected_release="2.0.11",
        profile_id="profile-a",
        client=httpx.AsyncClient(transport=httpx.MockTransport(overloaded)),
    )
    with pytest.raises(CapacityExceededFailure) as raised:
        await adapter.generate_task(task(TextInput("hello")))
    assert "secret upstream body" not in str(raised.value)
