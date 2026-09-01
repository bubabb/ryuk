import pytest

from backend.inference.base import InferenceRequest
from backend.inference.engines.mock import MockEngine


@pytest.mark.asyncio
async def test_mock_engine_returns_normalized_deterministic_response() -> None:
    response = await MockEngine().generate(
        InferenceRequest(prompt="Explain Ryuk", model="test-model")
    )

    assert response.text == "Mock response for: Explain Ryuk"
    assert response.model == "test-model"
    assert response.engine == "mock"
    assert response.metadata == {
        "mock": True,
        "production": False,
        "warning": "Deterministic development output; no model executed.",
    }
