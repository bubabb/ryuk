import json

import httpx
import pytest

from backend.inference.capabilities import (
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
)
from backend.inference.contracts import (
    AttemptOutcome,
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
from backend.inference.deployment import DeploymentRef, ModelRef
from backend.inference.engines.dynamo import DynamoEngine
from backend.inference.engines.nim import NIMEngine, NVIDIAHostedNIMEngine
from backend.inference.errors import (
    CapacityExceededFailure,
    UnsupportedTaskFailure,
    UpstreamProtocolFailure,
)
from backend.inference.registry import DeploymentRegistry, RegisteredDeployment
from backend.inference.router import InferenceRouter


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
async def test_hosted_nim_uses_catalog_models_for_readiness_and_identity() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={"data": [{"id": "moonshotai/kimi-k3"}]},
            )
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "hosted-response-1",
                "model": "moonshotai/kimi-k3",
                "choices": [
                    {"message": {"content": "ready"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )

    adapter = NVIDIAHostedNIMEngine(
        "https://integrate.api.nvidia.com",
        model="moonshotai/kimi-k3",
        api_key="test-key",
        reasoning_effort="low",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert await adapter.is_available()
    identity = await adapter.discover_model_identity()
    assert identity.observation.model.artifact_id == "moonshotai/kimi-k3"
    result = await adapter.generate_task(
        task(ChatInput((ChatMessage(ChatRole.USER, "reply ready"),)))
    )
    assert captured["reasoning_effort"] == "low"
    assert result.output.text == "ready"
    assert result.adapter_metadata["nvidia-hosted-nim"]["served_model"] == (
        "moonshotai/kimi-k3"
    )


@pytest.mark.asyncio
async def test_hosted_nim_rejects_unsupported_text_completion() -> None:
    async def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"No hosted request expected: {request.url.path}")

    adapter = NVIDIAHostedNIMEngine(
        "https://integrate.api.nvidia.com",
        model="moonshotai/kimi-k3",
        client=httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)),
    )

    with pytest.raises(UnsupportedTaskFailure):
        await adapter.generate_task(task(TextInput("hello")))


def test_hosted_nim_requires_an_exact_supported_model_profile() -> None:
    with pytest.raises(ValueError, match="supported exact model profile"):
        NVIDIAHostedNIMEngine(
            "https://integrate.api.nvidia.com",
            model="moving-or-unknown-alias",
        )


@pytest.mark.asyncio
async def test_hosted_nim_rejects_malformed_reasoning_without_leaking_it() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "ready",
                            "reasoning_content": {"private": "not text"},
                        }
                    }
                ]
            },
        )

    adapter = NVIDIAHostedNIMEngine(
        "https://integrate.api.nvidia.com",
        model="moonshotai/kimi-k3",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(UpstreamProtocolFailure) as raised:
        await adapter.generate_task(
            task(ChatInput((ChatMessage(ChatRole.USER, "reply ready"),)))
        )
    assert raised.value.context["reason"] == "invalid_reasoning"
    assert "private" not in str(raised.value)


@pytest.mark.asyncio
async def test_hosted_nim_generation_failure_fails_over_between_models() -> None:
    first_model = "moonshotai/kimi-k3"
    second_model = "deepseek-ai/deepseek-v4-flash-0731"

    def transport(model: str, *, fail_generation: bool) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/models":
                return httpx.Response(
                    200,
                    json={"data": [{"id": first_model}, {"id": second_model}]},
                )
            if fail_generation:
                return httpx.Response(503, text="upstream details must stay private")
            return httpx.Response(
                200,
                json={
                    "id": "fallback-response",
                    "model": model,
                    "choices": [
                        {
                            "message": {
                                "content": "ready",
                                "reasoning": "separate reasoning",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 1},
                },
            )

        return httpx.MockTransport(handler)

    deployments = DeploymentRegistry()
    engines: list[NVIDIAHostedNIMEngine] = []
    for sequence, (model, fails) in enumerate(
        ((first_model, True), (second_model, False)), start=1
    ):
        engine = NVIDIAHostedNIMEngine(
            "https://integrate.api.nvidia.com",
            model=model,
            client=httpx.AsyncClient(transport=transport(model, fail_generation=fails)),
        )
        engines.append(engine)
        deployments.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=f"hosted-nim-{sequence}",
                    model=ModelRef(model, served_name=model),
                    engine_name=engine.name,
                    endpoint_id=f"nvidia-catalog-{sequence}",
                    serving_runtime="nvidia_dgx_cloud_hosted_nim",
                ),
                engine=engine,
                capabilities=DeploymentCapabilities(
                    task_kinds=configured_claim(frozenset({TaskKind.CHAT}), "test"),
                    served_models=configured_claim(frozenset({model}), "test"),
                ),
            )
        )

    result = await InferenceRouter(deployments).generate_task(
        task(ChatInput((ChatMessage(ChatRole.USER, "reply ready"),)))
    )

    assert result.output.text == "ready"
    assert result.reasoning is not None
    assert result.reasoning.text == "separate reasoning"
    assert result.provenance.model_artifact_id == second_model
    assert [attempt.outcome for attempt in result.attempts] == [
        AttemptOutcome.FAILED,
        AttemptOutcome.SUCCEEDED,
    ]
    assert result.attempts[0].failure_code == "capacity_exceeded"


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
