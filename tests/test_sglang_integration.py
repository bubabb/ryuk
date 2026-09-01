import os

import pytest

from backend.inference.engines.sglang import SGLangEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_sglang_health_and_identity_contract() -> None:
    base_url = os.getenv("SGLANG_TEST_BASE_URL")
    if not base_url:
        pytest.skip("Set SGLANG_TEST_BASE_URL to run the real-server contract test.")

    async with SGLangEngine(base_url=base_url) as engine:
        assert await engine.is_available()
        discovery = await engine.discover_model_identity()

    assert discovery.observation.model.artifact_id
