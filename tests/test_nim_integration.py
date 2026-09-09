import os

import pytest

from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.engines.nim import NIMEngine, NVIDIAHostedNIMEngine
from backend.inference.errors import InferenceFailure


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_nim_contract() -> None:
    base_url = os.getenv("NIM_TEST_BASE_URL")
    model = os.getenv("NIM_TEST_MODEL")
    release = os.getenv("NIM_TEST_RELEASE")
    profile = os.getenv("NIM_TEST_PROFILE_ID")
    if not all((base_url, model, release, profile)):
        pytest.skip("NIM_TEST_BASE_URL/model/release/profile are not configured")
    assert base_url is not None
    assert model is not None
    assert release is not None
    assert profile is not None
    adapter = NIMEngine(
        base_url,
        model=model,
        expected_release=release,
        profile_id=profile,
        api_key=os.getenv("NIM_TEST_API_KEY", ""),
    )
    try:
        assert await adapter.is_available()
        identity = await adapter.discover_model_identity()
        assert identity.observation.model.artifact_id == model
        result = await adapter.generate_task(
            InferenceTask(
                input=TextInput("Reply with exactly: ryuk-nim-ok"),
                generation=GenerationConfig(max_output_tokens=16, temperature=0),
                requirements=TaskRequirements(required_model=model),
                trace=TraceContext("nim-integration-contract"),
            )
        )
        assert result.output.text.strip()
    finally:
        await adapter.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_real_nvidia_hosted_nim_models() -> None:
    api_key = os.getenv("NVIDIA_API_KEY")
    models = tuple(
        value.strip()
        for value in os.getenv(
            "NVIDIA_HOSTED_NIM_MODELS",
            "moonshotai/kimi-k3,deepseek-ai/deepseek-v4-flash-0731",
        ).split(",")
        if value.strip()
    )
    if not api_key:
        pytest.skip("Set NVIDIA_API_KEY to run hosted NVIDIA NIM contracts")
    if len(models) != 2:
        pytest.fail("NVIDIA_HOSTED_NIM_MODELS must contain exactly two models")

    for sequence, model in enumerate(models, start=1):
        adapter = NVIDIAHostedNIMEngine(
            "https://integrate.api.nvidia.com",
            model=model,
            api_key=api_key,
            reasoning_effort="low" if model == "moonshotai/kimi-k3" else None,
        )
        try:
            assert await adapter.is_available(), f"hosted model unavailable: {model}"
            try:
                identity = await adapter.discover_model_identity()
            except InferenceFailure as exc:
                pytest.fail(f"hosted model identity failed for {model}: {exc}")
            assert identity.observation.model.artifact_id == model
            result = await adapter.generate_task(
                InferenceTask(
                    input=ChatInput(
                        (ChatMessage(ChatRole.USER, "Reply with exactly: ready"),)
                    ),
                    generation=GenerationConfig(
                        max_output_tokens=1024,
                        temperature=0,
                    ),
                    requirements=TaskRequirements(required_model=model),
                    trace=TraceContext(f"nvidia-hosted-{sequence}"),
                )
            )
            assert result.output.text.strip()
        finally:
            await adapter.aclose()
