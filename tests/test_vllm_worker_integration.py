import os

import pytest

from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.engines.vllm_worker import VLLMWorkerEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_vllm_worker_contract() -> None:
    base_url = os.getenv("VLLM_WORKER_TEST_BASE_URL")
    if not base_url:
        pytest.skip("Set VLLM_WORKER_TEST_BASE_URL to run the GPU-worker test.")
    engine = VLLMWorkerEngine(base_url)
    try:
        assert await engine.is_available()
        identity = await engine.discover_model_identity()
        result = await engine.generate_task(
            InferenceTask(
                input=TextInput("Reply with the word ready."),
                generation=GenerationConfig(max_output_tokens=8, temperature=0.0),
                requirements=TaskRequirements(
                    required_model=identity.observation.model.artifact_id
                ),
                trace=TraceContext(request_id="vllm-integration-1"),
            )
        )
        assert result.output.text
    finally:
        await engine.aclose()
