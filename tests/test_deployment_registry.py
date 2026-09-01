import pytest

from backend.config import AppEnvironment, Settings
from backend.inference.deployment import (
    DeploymentRef,
    IdentityVerification,
    ModelRef,
)
from backend.inference.engines.mock import MockEngine
from backend.inference.registry import (
    DeploymentRegistry,
    RegisteredDeployment,
    build_deployment_registry,
    build_engine_registry,
)


def mock_deployment(deployment_id: str = "mock-one") -> RegisteredDeployment:
    return RegisteredDeployment(
        ref=DeploymentRef(
            deployment_id=deployment_id,
            model=ModelRef("ryuk/mock", served_name="mock"),
            engine_name="mock",
            serving_runtime="in_process",
            endpoint_id="mock-in-process",
        ),
        engine=MockEngine(),
    )


def test_deployment_registry_is_case_insensitive() -> None:
    registry = DeploymentRegistry()
    registry.register(mock_deployment("Mock-One"))

    assert registry.get("mock-one").ref.deployment_id == "Mock-One"
    assert registry.ids() == ("mock-one",)


def test_deployment_registry_rejects_duplicate_ids() -> None:
    registry = DeploymentRegistry()
    registry.register(mock_deployment("mock-one"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(mock_deployment("MOCK-ONE"))


def test_registered_deployment_rejects_engine_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="engine_name"):
        RegisteredDeployment(
            ref=DeploymentRef(
                deployment_id="invalid",
                model=ModelRef("model"),
                engine_name="sglang",
                endpoint_id="endpoint",
            ),
            engine=MockEngine(),
        )


def test_builder_registers_explicit_sglang_and_mock_deployments() -> None:
    config = Settings(
        app_env=AppEnvironment.TEST,
        sglang_enabled=True,
        sglang_model_artifact_id="moonshotai/Kimi-K2",
        sglang_model_revision="revision-1",
        sglang_served_model_name="kimi-k2",
        sglang_engine_version="0.5.18",
        mock_enabled=True,
    )

    registry = build_deployment_registry(config)

    assert registry.ids() == ("mock-development", "sglang-local")
    sglang = registry.get("sglang-local").ref
    assert sglang.model == ModelRef(
        artifact_id="moonshotai/Kimi-K2",
        revision="revision-1",
        served_name="kimi-k2",
    )
    assert sglang.engine_version == "0.5.18"


def test_unconfigured_sglang_model_remains_unknown() -> None:
    config = Settings(
        app_env=AppEnvironment.TEST,
        sglang_enabled=True,
        sglang_model_artifact_id="",
        mock_enabled=False,
    )

    deployment = build_deployment_registry(config).get("sglang-local")

    assert deployment.ref.model is None


def test_builder_registers_vllm_worker_with_truthful_identity() -> None:
    config = Settings(
        app_env=AppEnvironment.TEST,
        sglang_enabled=False,
        mock_enabled=False,
        vllm_enabled=True,
        vllm_model_artifact_id="moonshotai/Kimi-K2-Instruct",
        vllm_model_revision="revision-1",
        vllm_accelerators="h100",
    )

    deployment = build_deployment_registry(config).get("vllm-worker")

    assert deployment.ref.engine_name == "vllm"
    assert deployment.ref.engine_version == "0.26.0"
    assert deployment.ref.model == ModelRef(
        "moonshotai/Kimi-K2-Instruct", revision="revision-1"
    )
    assert deployment.capabilities.accelerators is not None
    assert deployment.capabilities.accelerators.value == frozenset({"h100"})


def test_engine_registry_is_compatibility_view_of_deployments() -> None:
    config = Settings(
        app_env=AppEnvironment.TEST,
        sglang_enabled=False,
        mock_enabled=True,
    )

    assert build_engine_registry(config).names() == ("mock",)


@pytest.mark.asyncio
async def test_registered_mock_identity_is_verified() -> None:
    deployment = mock_deployment()

    inspection = await deployment.inspect_identity()

    assert inspection.assessment.status is IdentityVerification.VERIFIED
    assert inspection.discovery_error is None
