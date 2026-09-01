from typing import Any, cast

import pytest
from pydantic import ValidationError

from backend.config import AppEnvironment, Settings
from backend.inference.engines.dynamo import DynamoEngine
from backend.inference.engines.nim import NIMEngine
from backend.inference.registry import build_deployment_registry


def base_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": AppEnvironment.TEST,
        "sglang_enabled": False,
        "vllm_enabled": False,
        "mock_enabled": False,
    }
    values.update(overrides)
    return Settings(**cast(Any, values))


def test_dynamo_registry_represents_whole_deployment() -> None:
    registry = build_deployment_registry(
        base_settings(
            dynamo_enabled=True,
            dynamo_model_artifact_id="moonshotai/Kimi-K2.5",
            dynamo_model_revision="revision-a",
            dynamo_topology="disaggregated",
        )
    )
    deployment = registry.get("dynamo-deployment")
    assert isinstance(deployment.engine, DynamoEngine)
    assert deployment.ref.serving_runtime == "dynamo_disaggregated"
    assert deployment.ref.model is not None
    assert deployment.ref.model.revision == "revision-a"


def test_nim_registry_records_release_profile_and_backend() -> None:
    registry = build_deployment_registry(
        base_settings(
            nim_enabled=True,
            nim_model_artifact_id="model-a",
            nim_profile_id="profile-a",
        )
    )
    deployment = registry.get("nim-deployment")
    assert isinstance(deployment.engine, NIMEngine)
    assert deployment.ref.engine_version == "2.0.11"
    assert deployment.ref.serving_runtime == "nim_vllm"


@pytest.mark.parametrize(
    "values",
    [
        {"dynamo_enabled": True},
        {"nim_enabled": True, "nim_model_artifact_id": "model-a"},
        {"nim_enabled": True, "nim_profile_id": "profile-a"},
        {"dynamo_production_eligible": True},
        {"tensorrt_llm_enabled": True},
    ],
)
def test_managed_deployments_fail_closed_without_identity_pins(values) -> None:
    with pytest.raises(ValidationError):
        base_settings(**values)
