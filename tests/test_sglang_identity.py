import httpx
import pytest

from backend.inference.deployment import IdentityVerification, ModelRef
from backend.inference.engines.sglang import (
    SGLangEngine,
    SGLangIdentityDiscoveryError,
)
from backend.inference.errors import DeploymentUnavailableFailure


def engine(response: httpx.Response | Exception) -> SGLangEngine:
    async def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SGLangEngine(base_url="http://sglang.test", client=client)


@pytest.mark.asyncio
async def test_discovers_and_assesses_native_model_identity() -> None:
    payload = {
        "model_path": "moonshotai/Kimi-K2",
        "served_model_name": "kimi-k2",
        "weight_version": "revision-1",
        "architectures": ["KimiForCausalLM"],
    }
    adapter = engine(httpx.Response(200, json=payload))

    discovery = await adapter.discover_model_identity(
        use_weight_version_as_revision=True
    )
    assessment = await adapter.assess_model_identity(
        ModelRef("moonshotai/Kimi-K2", served_name="kimi-k2")
    )

    assert discovery.observation.model == ModelRef(
        "moonshotai/Kimi-K2", revision="revision-1", served_name="kimi-k2"
    )
    assert discovery.adapter_metadata == {"model_info": payload}
    assert assessment.status is IdentityVerification.VERIFIED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"served_model_name": "kimi-k2"}, "missing_model_path"),
        ({"model_path": "model", "served_model_name": ["bad"]}, "invalid_field"),
    ],
)
async def test_rejects_invalid_identity_schema(payload: object, reason: str) -> None:
    with pytest.raises(SGLangIdentityDiscoveryError) as raised:
        await engine(httpx.Response(200, json=payload)).discover_model_identity()
    assert raised.value.context["reason"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, content=b"not-json"), "invalid_json"),
        (httpx.Response(200, json=["model"]), "non_object_json"),
    ],
)
async def test_rejects_invalid_identity_json(
    response: httpx.Response, reason: str
) -> None:
    with pytest.raises(SGLangIdentityDiscoveryError) as raised:
        await engine(response).discover_model_identity()
    assert raised.value.context["reason"] == reason


@pytest.mark.asyncio
async def test_identity_network_failure_is_safe() -> None:
    request = httpx.Request("GET", "http://sglang.test/model_info")
    adapter = engine(httpx.ConnectError("credential-secret", request=request))
    with pytest.raises(DeploymentUnavailableFailure) as raised:
        await adapter.discover_model_identity()
    assert "credential-secret" not in str(raised.value)


@pytest.mark.asyncio
async def test_health_uses_status_and_contains_transport_failure() -> None:
    assert await engine(httpx.Response(503)).is_available() is False
    request = httpx.Request("GET", "http://sglang.test/health")
    offline = engine(httpx.ConnectError("offline", request=request))
    assert await offline.is_available() is False
