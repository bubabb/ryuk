import asyncio

import httpx
import pytest

from backend.inference.base import InferenceRequest
from backend.inference.engines.sglang import SGLangEngine
from backend.inference.errors import (
    CapacityExceededFailure,
    DeadlineExceededFailure,
    DeploymentUnavailableFailure,
    GenerationFailure,
    UpstreamProtocolFailure,
)


def engine(response: httpx.Response | Exception, *, limit: int = 1024) -> SGLangEngine:
    async def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SGLangEngine(
        base_url="http://sglang.test", client=client, max_response_bytes=limit
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "failure_type"),
    [
        (503, CapacityExceededFailure),
        (504, DeadlineExceededFailure),
        (500, GenerationFailure),
        (400, UpstreamProtocolFailure),
    ],
)
async def test_generation_classifies_http_failures(
    status: int, failure_type: type[Exception]
) -> None:
    with pytest.raises(failure_type) as raised:
        await engine(httpx.Response(status, text="credential-secret")).generate(
            InferenceRequest(prompt="hello", model="model")
        )
    assert "credential-secret" not in str(raised.value)


@pytest.mark.asyncio
async def test_generation_classifies_timeout_and_network_failure() -> None:
    request = httpx.Request("POST", "http://sglang.test/generate")
    with pytest.raises(DeadlineExceededFailure):
        await engine(httpx.ReadTimeout("slow", request=request)).generate(
            InferenceRequest(prompt="hello", model="model")
        )
    with pytest.raises(DeploymentUnavailableFailure):
        await engine(httpx.ConnectError("offline", request=request)).generate(
            InferenceRequest(prompt="hello", model="model")
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, content=b"not-json"), "invalid_json"),
        (httpx.Response(200, json=["bad"]), "non_object_json"),
        (httpx.Response(200, json={"text": 3}), "invalid_schema"),
    ],
)
async def test_generation_rejects_invalid_responses(
    response: httpx.Response, reason: str
) -> None:
    with pytest.raises(UpstreamProtocolFailure) as raised:
        await engine(response).generate(InferenceRequest(prompt="hello", model="model"))
    assert raised.value.context["reason"] == reason


@pytest.mark.asyncio
async def test_generation_enforces_response_size_limit() -> None:
    with pytest.raises(UpstreamProtocolFailure) as raised:
        await engine(httpx.Response(200, content=b"x" * 20), limit=10).generate(
            InferenceRequest(prompt="hello", model="model")
        )
    assert raised.value.context["reason"] == "response_too_large"


@pytest.mark.asyncio
async def test_generation_sends_request_id_and_normalizes_usage() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "text": "done",
                "meta_info": {
                    "prompt_tokens": 2,
                    "completion_tokens": 3,
                    "finish_reason": "stop",
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SGLangEngine(base_url="http://sglang.test", client=client)
    result = await adapter.generate(
        InferenceRequest(
            prompt="hello", model="model", metadata={"request_id": "request-1"}
        )
    )
    assert captured["rid"] == "request-1"
    assert result.input_tokens == 2
    assert result.output_tokens == 3
    assert result.metadata["sglang_finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_client_cancellation_propagates_to_transport() -> None:
    cancelled = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
        return httpx.Response(200, json={"text": "late"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SGLangEngine(base_url="http://sglang.test", client=client)
    operation = asyncio.create_task(
        adapter.generate(InferenceRequest(prompt="hello", model="model"))
    )
    await asyncio.sleep(0)
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert cancelled.is_set()
