import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TraceContext,
)
from backend.inference.engines.nim import NVIDIAHostedNIMEngine
from backend.inference.errors import InferenceFailure
from backend.inference.profiles import load_offline_deployment_profiles

FIXTURE_DIRECTORY = Path("tests/fixtures/phase2a")
PROFILE_DIRECTORY = Path("deployments/offline")
FIXTURE_PATHS = tuple(sorted(FIXTURE_DIRECTORY.glob("*.json")))
REQUIRED_CASES = {
    "success_with_usage",
    "overload",
    "timeout",
    "malformed_choices",
    "response_limit",
}
FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "set-cookie",
    "token",
}


def load_fixture(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(result, dict)
    return result


def inference_task(model: str) -> InferenceTask:
    return InferenceTask(
        input=ChatInput((ChatMessage(ChatRole.USER, "Reply with exactly: ready"),)),
        generation=GenerationConfig(max_output_tokens=16, temperature=0),
        requirements=TaskRequirements(required_model=model),
        trace=TraceContext("phase2a-fixture-request"),
    )


def assert_sanitized(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key.casefold() not in FORBIDDEN_KEYS
            assert_sanitized(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_sanitized(nested)
    elif isinstance(value, str):
        lowered = value.casefold()
        assert "bearer " not in lowered
        assert "nvapi-" not in lowered
        assert "sk-" not in lowered


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS)
def test_phase2a_fixture_is_complete_linked_and_sanitized(
    fixture_path: Path,
) -> None:
    fixture = load_fixture(fixture_path)
    profiles = {
        profile.profile_id: profile
        for profile in load_offline_deployment_profiles(PROFILE_DIRECTORY)
    }

    assert fixture["fixture_version"] == "phase2a-hosted-contract-v1"
    assert fixture["profile_id"] in profiles
    assert fixture["model"] == profiles[fixture["profile_id"]].served_model_name
    assert {case["id"] for case in fixture["cases"]} == REQUIRED_CASES
    assert_sanitized(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS)
async def test_phase2a_fixture_normalizes_identity_success_and_usage(
    fixture_path: Path,
) -> None:
    fixture = load_fixture(fixture_path)
    success = next(
        case for case in fixture["cases"] if case["id"] == "success_with_usage"
    )
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            identity = fixture["identity"]
            return httpx.Response(identity["status"], json=identity["response"])
        captured.update(json.loads(request.content))
        return httpx.Response(success["status"], json=success["response"])

    adapter = NVIDIAHostedNIMEngine(
        "https://integrate.api.nvidia.com",
        model=fixture["model"],
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    identity = await adapter.discover_model_identity()
    result = await adapter.generate_task(inference_task(fixture["model"]))

    assert identity.observation.model.artifact_id == fixture["model"]
    assert captured["model"] == fixture["model"]
    assert captured["stream"] is False
    assert result.output.text == success["expected"]["text"]
    assert result.usage.input_tokens == success["expected"]["input_tokens"]
    assert result.usage.output_tokens == success["expected"]["output_tokens"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS)
@pytest.mark.parametrize(
    "case_id", ("overload", "timeout", "malformed_choices", "response_limit")
)
async def test_phase2a_fixture_normalizes_failures(
    fixture_path: Path,
    case_id: str,
) -> None:
    fixture = load_fixture(fixture_path)
    case = next(item for item in fixture["cases"] if item["id"] == case_id)

    async def handler(request: httpx.Request) -> httpx.Response:
        if case["behavior"] == "read_timeout":
            raise httpx.ReadTimeout("sanitized fixture timeout", request=request)
        if case["behavior"] == "oversized_response":
            return httpx.Response(200, content=b"x" * 256)
        return httpx.Response(case["status"], json=case["response"])

    adapter = NVIDIAHostedNIMEngine(
        "https://integrate.api.nvidia.com",
        model=fixture["model"],
        max_response_bytes=case.get("max_response_bytes", 1024),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(InferenceFailure) as raised:
        await adapter.generate_task(inference_task(fixture["model"]))
    assert raised.value.code == case["expected_failure"]
    assert "sanitized overload" not in str(raised.value)
    assert "sanitized fixture timeout" not in str(raised.value)
