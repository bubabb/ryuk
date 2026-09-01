import os

import pytest

from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.engines.dynamo import DynamoEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_dynamo_frontend_contract() -> None:
    base_url = os.getenv("DYNAMO_TEST_BASE_URL")
    model = os.getenv("DYNAMO_TEST_MODEL")
    version = os.getenv("DYNAMO_TEST_VERSION")
    topology = os.getenv("DYNAMO_TEST_TOPOLOGY", "aggregated")
    if not all((base_url, model, version)):
        pytest.skip("DYNAMO_TEST_BASE_URL/model/version are not configured")
    assert base_url is not None
    assert model is not None
    assert version is not None
    adapter = DynamoEngine(
        base_url,
        model=model,
        runtime_version=version,
        topology=topology,
    )
    try:
        assert await adapter.is_available()
        identity = await adapter.discover_model_identity()
        assert identity.observation.model.artifact_id == model
        result = await adapter.generate_task(
            InferenceTask(
                input=TextInput("Reply with exactly: ryuk-dynamo-ok"),
                generation=GenerationConfig(max_output_tokens=16, temperature=0),
                requirements=TaskRequirements(required_model=model),
                trace=TraceContext("dynamo-integration-contract"),
            )
        )
        assert result.output.text.strip()
        assert result.adapter_metadata["dynamo"]["topology"] == topology
    finally:
        await adapter.aclose()
