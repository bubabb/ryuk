import os

import pytest

from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.engines.nim import NIMEngine


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
