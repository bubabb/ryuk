from pathlib import Path
from typing import Any

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
    configured = Settings(
        app_env=AppEnvironment.PRODUCTION,
        mock_enabled=False,
        control_plane_config_path=Path("control.json"),
        database_url="postgresql://db/ryuk",
        redis_url="redis://redis/0",
    )

    assert configured.app_env is AppEnvironment.PRODUCTION


def test_production_requires_control_configuration_and_durable_records() -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(app_env=AppEnvironment.PRODUCTION, mock_enabled=False)


def test_production_rejects_inline_provider_credentials() -> None:
    with pytest.raises(ValidationError, match="secret references"):
        Settings(
            app_env=AppEnvironment.PRODUCTION,
            mock_enabled=False,
            control_plane_config_path=Path("control.json"),
            database_url="postgresql://db/ryuk",
            redis_url="redis://redis/0",
            nim_api_key="plaintext-secret",
        )


def test_production_nim_requires_secret_reference() -> None:
    with pytest.raises(ValidationError, match="NIM_SECRET_REF"):
        Settings(
            app_env=AppEnvironment.PRODUCTION,
            mock_enabled=False,
            sglang_enabled=False,
            control_plane_config_path=Path("control.json"),
            database_url="postgresql://db/ryuk",
            redis_url="redis://redis/0",
            nim_enabled=True,
            nim_model_artifact_id="model-a",
            nim_profile_id="profile-a",
        )


def test_production_nim_requires_vault_reference_and_https_address() -> None:
    common: dict[str, Any] = {
        "app_env": AppEnvironment.PRODUCTION,
        "mock_enabled": False,
        "sglang_enabled": False,
        "control_plane_config_path": Path("control.json"),
        "database_url": "postgresql://db/ryuk",
        "redis_url": "redis://redis/0",
        "nim_enabled": True,
        "nim_model_artifact_id": "model-a",
        "nim_profile_id": "profile-a",
    }
    with pytest.raises(ValidationError, match="vault"):
        Settings(**common, nim_secret_ref="env:NIM_API_KEY")
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            **common,
            nim_secret_ref="vault:secret/data/ryuk/nim#api_key",
            vault_address="http://vault.internal",
        )

    configured = Settings(
        **common,
        nim_secret_ref="vault:secret/data/ryuk/nim#api_key",
        vault_address="https://vault.internal",
    )
    assert configured.nim_secret_ref.startswith("vault:")


def test_vllm_requires_explicit_model_identity() -> None:
    with pytest.raises(ValidationError, match="VLLM_MODEL_ARTIFACT_ID is required"):
        Settings(vllm_enabled=True, vllm_model_artifact_id="")
