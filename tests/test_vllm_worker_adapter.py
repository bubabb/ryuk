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
from backend.inference.engines.vllm_worker import VLLMWorkerEngine
from backend.inference.errors import CapacityExceededFailure, UpstreamProtocolFailure


def task(input_value: TextInput | ChatInput) -> InferenceTask:
    return InferenceTask(
        input=input_value,
        generation=GenerationConfig(max_output_tokens=12, temperature=0.2),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
    )


@pytest.mark.asyncio
async def test_native_worker_text_contract_and_normalization() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "text": "done",
                "finish_reason": "stop",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "latency_ms": 4.0,
                "metadata": {"runtime": "vllm"},
            },
        )

    adapter = VLLMWorkerEngine(
        "http://worker",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await adapter.generate_task(task(TextInput("hello")))

    assert captured["request_id"] == "request-1"
    assert captured["input"] == {"kind": "text", "text": "hello"}
    assert result.output.text == "done"
    assert result.finish_reason is FinishReason.STOP
    assert result.usage.output_tokens == 3


@pytest.mark.asyncio
async def test_native_worker_preserves_typed_chat_messages() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"text": "done", "usage": {}})

    adapter = VLLMWorkerEngine(
        "http://worker",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await adapter.generate_task(
        task(
            ChatInput(
                messages=(
                    ChatMessage(ChatRole.SYSTEM, "Be concise"),
                    ChatMessage(ChatRole.USER, "Hello"),
                )
            )
        )
    )

    assert captured["input"] == {
        "kind": "chat",
        "messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ],
    }


@pytest.mark.asyncio
async def test_worker_identity_and_health_are_native_contracts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("health"):
            return httpx.Response(200, json={"ready": True})
        return httpx.Response(
            200,
            json={
                "model_artifact_id": "moonshotai/Kimi-K2-Instruct",
                "model_revision": "revision-1",
                "engine_version": "0.26.0",
            },
        )

    adapter = VLLMWorkerEngine(
        "http://worker",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await adapter.is_available()
    identity = await adapter.discover_model_identity()
    assert identity.observation.model.artifact_id == "moonshotai/Kimi-K2-Instruct"
    assert identity.observation.model.revision == "revision-1"


@pytest.mark.asyncio
async def test_worker_failures_are_typed_and_bodies_are_safe() -> None:
    async def overloaded(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="credential-secret")

    adapter = VLLMWorkerEngine(
        "http://worker",
        client=httpx.AsyncClient(transport=httpx.MockTransport(overloaded)),
    )
    with pytest.raises(CapacityExceededFailure) as raised:
        await adapter.generate_task(task(TextInput("hello")))
    assert "credential-secret" not in str(raised.value)

    async def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": 4})

    adapter = VLLMWorkerEngine(
        "http://worker",
        client=httpx.AsyncClient(transport=httpx.MockTransport(malformed)),
    )
    with pytest.raises(UpstreamProtocolFailure):
        await adapter.generate_task(task(TextInput("hello")))
