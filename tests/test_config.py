import pytest
from pydantic import ValidationError

from backend.config import AppEnvironment, Settings


def test_environment_is_typed() -> None:
    configured = Settings(app_env=AppEnvironment.TEST, mock_enabled=True)

    assert configured.app_env is AppEnvironment.TEST


def test_mock_is_rejected_in_production() -> None:
    with pytest.raises(
        ValidationError, match="MOCK_ENABLED must be false in production"
    ):
        Settings(app_env=AppEnvironment.PRODUCTION, mock_enabled=True)


def test_production_without_mock_is_valid() -> None:
    configured = Settings(app_env=AppEnvironment.PRODUCTION, mock_enabled=False)

    assert configured.app_env is AppEnvironment.PRODUCTION


def test_vllm_requires_explicit_model_identity() -> None:
    with pytest.raises(ValidationError, match="VLLM_MODEL_ARTIFACT_ID is required"):
        Settings(vllm_enabled=True, vllm_model_artifact_id="")
