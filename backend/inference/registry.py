from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.config import AppEnvironment, Settings, settings
from backend.inference.base import InferenceEngine
from backend.inference.capabilities import (
    CapabilityClaim,
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
)
from backend.inference.deployment import (
    DeploymentRef,
    IdentityDiscoveringEngine,
    IdentityInspection,
    ModelRef,
    assess_model_identity,
)
from backend.inference.engines.dynamo import DynamoEngine
from backend.inference.engines.mock import MockEngine
from backend.inference.engines.nim import NIMEngine
from backend.inference.engines.sglang import SGLangEngine
from backend.inference.engines.vllm_worker import VLLMWorkerEngine
from backend.inference.errors import InferenceFailure
from backend.inference.policy import CostClass, LatencyClass, RoutingPolicyProfile


@runtime_checkable
class AsyncClosingEngine(Protocol):
    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RegisteredDeployment:
    ref: DeploymentRef
    engine: InferenceEngine
    capabilities: DeploymentCapabilities = DeploymentCapabilities()
    policy_profile: RoutingPolicyProfile = RoutingPolicyProfile()

    def __post_init__(self) -> None:
        if self.ref.engine_name.lower() != self.engine.name.lower():
            raise ValueError(
                "Deployment engine_name must match the registered engine name."
            )

    async def inspect_identity(self) -> IdentityInspection:
        if not isinstance(self.engine, IdentityDiscoveringEngine):
            return IdentityInspection(
                assessment=assess_model_identity(self.ref.model, None),
                discovery_error="identity_discovery_not_supported",
            )

        try:
            discovery = await self.engine.discover_model_identity()
        except InferenceFailure:
            return IdentityInspection(
                assessment=assess_model_identity(self.ref.model, None),
                discovery_error="identity_discovery_failed",
            )

        return IdentityInspection(
            assessment=assess_model_identity(
                self.ref.model,
                discovery.observation,
            )
        )


class DeploymentRegistry:
    """Stores executable deployments under Ryuk-owned identities."""

    def __init__(self) -> None:
        self._deployments: dict[str, RegisteredDeployment] = {}

    def register(self, deployment: RegisteredDeployment) -> None:
        key = deployment.ref.deployment_id.lower()
        if key in self._deployments:
            raise ValueError(
                f"Deployment '{deployment.ref.deployment_id}' is already registered."
            )
        self._deployments[key] = deployment

    def get(self, deployment_id: str) -> RegisteredDeployment:
        key = deployment_id.strip().lower()
        try:
            return self._deployments[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._deployments)) or "none"
            raise KeyError(
                f"Deployment '{deployment_id}' is not registered. "
                f"Registered deployments: {available}"
            ) from exc

    def all(self) -> tuple[RegisteredDeployment, ...]:
        return tuple(self._deployments.values())

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._deployments))

    def __len__(self) -> int:
        return len(self._deployments)

    async def aclose(self) -> None:
        for deployment in self.all():
            if isinstance(deployment.engine, AsyncClosingEngine):
                await deployment.engine.aclose()


class EngineRegistry:
    """

    Stores and manages inference engines available to Ryuk.

    """

    def __init__(self) -> None:
        self._engines: dict[str, InferenceEngine] = {}

    def register(self, engine: InferenceEngine) -> None:
        name = engine.name.strip().lower()

        if not name:
            raise ValueError("Inference engine must define a non-empty name.")

        self._engines[name] = engine

    def unregister(self, name: str) -> None:
        self._engines.pop(name.strip().lower(), None)

    def get(self, name: str) -> InferenceEngine:
        key = name.strip().lower()

        try:
            return self._engines[key]

        except KeyError as exc:
            available = ", ".join(sorted(self._engines)) or "none"

            raise KeyError(
                f"Inference engine '{name}' is not registered. "
                f"Registered engines: {available}"
            ) from exc

    def all(self) -> tuple[InferenceEngine, ...]:
        return tuple(self._engines.values())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._engines))

    def register_many(self, engines: Iterable[InferenceEngine]) -> None:
        for engine in engines:
            self.register(engine)

    def __contains__(self, name: str) -> bool:
        return name.strip().lower() in self._engines

    def __len__(self) -> int:
        return len(self._engines)


def _optional_identifier(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _configured_sglang_model(config: Settings) -> ModelRef | None:
    artifact_id = _optional_identifier(config.sglang_model_artifact_id)
    if artifact_id is None:
        return None
    return ModelRef(
        artifact_id=artifact_id,
        revision=_optional_identifier(config.sglang_model_revision),
        served_name=_optional_identifier(config.sglang_served_model_name),
    )


def _sglang_capabilities(config: Settings) -> DeploymentCapabilities:
    model = _configured_sglang_model(config)
    served_models = None
    if model is not None:
        identifiers = {model.artifact_id}
        if model.served_name is not None:
            identifiers.add(model.served_name)
        served_models = configured_claim(
            frozenset(identifiers), "deployment", config.sglang_engine_version or None
        )
    return DeploymentCapabilities(
        task_kinds=configured_claim(frozenset({TaskKind.TEXT}), "deployment"),
        served_models=served_models,
        max_context_tokens=(
            configured_claim(config.sglang_max_context_tokens, "deployment")
            if config.sglang_max_context_tokens is not None
            else None
        ),
        structured_output=configured_claim(False, "deployment"),
        streaming=configured_claim(False, "deployment"),
        accelerators=_configured_set_claim(config.sglang_accelerators),
        topologies=_configured_set_claim(config.sglang_topology),
        data_locations=_configured_set_claim(config.sglang_data_locations),
        production_eligible=configured_claim(
            config.sglang_production_eligible, "deployment"
        ),
    )


def _configured_set_claim(
    value: str,
) -> CapabilityClaim[frozenset[str]] | None:
    values = frozenset(item.strip() for item in value.split(",") if item.strip())
    return configured_claim(values, "deployment") if values else None


def _mock_capabilities() -> DeploymentCapabilities:
    return DeploymentCapabilities(
        task_kinds=configured_claim(
            frozenset({TaskKind.TEXT, TaskKind.CHAT}), "deployment"
        ),
        served_models=configured_claim(frozenset({"ryuk/mock", "mock"}), "deployment"),
        structured_output=configured_claim(False, "deployment"),
        streaming=configured_claim(False, "deployment"),
        production_eligible=configured_claim(False, "deployment"),
    )


def _vllm_capabilities(config: Settings) -> DeploymentCapabilities:
    model = _optional_identifier(config.vllm_model_artifact_id)
    return DeploymentCapabilities(
        task_kinds=configured_claim(
            frozenset({TaskKind.TEXT, TaskKind.CHAT}), "deployment", "0.26.0"
        ),
        served_models=(
            configured_claim(frozenset({model}), "deployment") if model else None
        ),
        max_context_tokens=(
            configured_claim(config.vllm_max_context_tokens, "deployment")
            if config.vllm_max_context_tokens is not None
            else None
        ),
        structured_output=configured_claim(False, "deployment"),
        streaming=configured_claim(False, "deployment"),
        accelerators=_configured_set_claim(config.vllm_accelerators),
        topologies=_configured_set_claim(config.vllm_topology),
        data_locations=_configured_set_claim(config.vllm_data_locations),
        production_eligible=configured_claim(
            config.vllm_production_eligible, "deployment"
        ),
    )


def _managed_capabilities(
    *,
    model: str,
    version: str,
    max_context_tokens: int | None,
    accelerators: str,
    topology: str,
    data_locations: str,
    production_eligible: bool,
) -> DeploymentCapabilities:
    return DeploymentCapabilities(
        task_kinds=configured_claim(
            frozenset({TaskKind.TEXT, TaskKind.CHAT}), "deployment", version
        ),
        served_models=configured_claim(frozenset({model}), "deployment", version),
        max_context_tokens=(
            configured_claim(max_context_tokens, "deployment", version)
            if max_context_tokens is not None
            else None
        ),
        structured_output=configured_claim(False, "deployment", version),
        streaming=configured_claim(False, "deployment", version),
        accelerators=_configured_set_claim(accelerators),
        topologies=_configured_set_claim(topology),
        data_locations=_configured_set_claim(data_locations),
        production_eligible=configured_claim(
            production_eligible, "deployment", version
        ),
    )


def build_deployment_registry(
    config: Settings = settings,
) -> DeploymentRegistry:
    registry = DeploymentRegistry()

    if config.dynamo_enabled:
        model_id = config.dynamo_model_artifact_id.strip()
        registry.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=config.dynamo_deployment_id,
                    model=ModelRef(
                        model_id,
                        revision=_optional_identifier(config.dynamo_model_revision),
                    ),
                    engine_name="dynamo",
                    endpoint_id=config.dynamo_endpoint_id,
                    engine_version=config.dynamo_runtime_version,
                    serving_runtime=f"dynamo_{config.dynamo_topology}",
                ),
                engine=DynamoEngine(
                    config.dynamo_base_url,
                    model=model_id,
                    topology=config.dynamo_topology,
                    runtime_version=config.dynamo_runtime_version,
                ),
                capabilities=_managed_capabilities(
                    model=model_id,
                    version=config.dynamo_runtime_version,
                    max_context_tokens=config.dynamo_max_context_tokens,
                    accelerators=config.dynamo_accelerators,
                    topology=config.dynamo_topology,
                    data_locations=config.dynamo_data_locations,
                    production_eligible=config.dynamo_production_eligible,
                ),
                policy_profile=RoutingPolicyProfile(
                    cost_class=CostClass(config.dynamo_cost_class),
                    latency_class=LatencyClass(config.dynamo_latency_class),
                    text_suitability=5,
                    chat_suitability=5,
                ),
            )
        )

    if config.nim_enabled:
        model_id = config.nim_model_artifact_id.strip()
        registry.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=config.nim_deployment_id,
                    model=ModelRef(
                        model_id,
                        revision=_optional_identifier(config.nim_model_revision),
                    ),
                    engine_name="nim",
                    endpoint_id=config.nim_endpoint_id,
                    engine_version=config.nim_release,
                    serving_runtime=f"nim_{config.nim_backend}",
                ),
                engine=NIMEngine(
                    config.nim_base_url,
                    model=model_id,
                    api_key=config.nim_api_key,
                    expected_release=config.nim_release,
                    profile_id=config.nim_profile_id,
                ),
                capabilities=_managed_capabilities(
                    model=model_id,
                    version=config.nim_release,
                    max_context_tokens=config.nim_max_context_tokens,
                    accelerators=config.nim_accelerators,
                    topology=config.nim_topology,
                    data_locations=config.nim_data_locations,
                    production_eligible=config.nim_production_eligible,
                ),
                policy_profile=RoutingPolicyProfile(
                    cost_class=CostClass(config.nim_cost_class),
                    latency_class=LatencyClass(config.nim_latency_class),
                    text_suitability=5,
                    chat_suitability=5,
                ),
            )
        )

    if config.vllm_enabled:
        vllm_model_id = _optional_identifier(config.vllm_model_artifact_id)
        registry.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=config.vllm_deployment_id,
                    model=(
                        ModelRef(
                            vllm_model_id,
                            revision=_optional_identifier(config.vllm_model_revision),
                        )
                        if vllm_model_id
                        else None
                    ),
                    engine_name="vllm",
                    engine_version=config.vllm_engine_version,
                    serving_runtime="ryuk_vllm_worker",
                    endpoint_id=config.vllm_endpoint_id,
                ),
                engine=VLLMWorkerEngine(config.vllm_base_url),
                capabilities=_vllm_capabilities(config),
                policy_profile=RoutingPolicyProfile(
                    cost_class=CostClass(config.vllm_cost_class),
                    latency_class=LatencyClass(config.vllm_latency_class),
                    text_suitability=config.vllm_text_suitability,
                    chat_suitability=config.vllm_chat_suitability,
                ),
            )
        )

    if config.sglang_enabled:
        registry.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=config.sglang_deployment_id,
                    model=_configured_sglang_model(config),
                    engine_name="sglang",
                    engine_version=_optional_identifier(config.sglang_engine_version),
                    serving_runtime=config.sglang_serving_runtime,
                    endpoint_id=config.sglang_endpoint_id,
                ),
                engine=SGLangEngine(
                    base_url=config.sglang_base_url,
                    connect_timeout=config.sglang_connect_timeout_seconds,
                    read_timeout=config.sglang_read_timeout_seconds,
                    write_timeout=config.sglang_write_timeout_seconds,
                    pool_timeout=config.sglang_pool_timeout_seconds,
                    identity_timeout=config.sglang_identity_timeout_seconds,
                    max_response_bytes=config.sglang_max_response_bytes,
                ),
                capabilities=_sglang_capabilities(config),
                policy_profile=RoutingPolicyProfile(
                    cost_class=CostClass(config.sglang_cost_class),
                    latency_class=LatencyClass(config.sglang_latency_class),
                    text_suitability=config.sglang_text_suitability,
                ),
            )
        )

    if config.mock_enabled and config.app_env in {
        AppEnvironment.DEVELOPMENT,
        AppEnvironment.TEST,
    }:
        registry.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=config.mock_deployment_id,
                    model=ModelRef(
                        artifact_id="ryuk/mock",
                        served_name="mock",
                    ),
                    engine_name="mock",
                    serving_runtime="in_process",
                    endpoint_id="mock-in-process",
                ),
                engine=MockEngine(),
                capabilities=_mock_capabilities(),
                policy_profile=RoutingPolicyProfile(
                    cost_class=CostClass.LOW,
                    latency_class=LatencyClass.LOW,
                    text_suitability=-10,
                    chat_suitability=-10,
                ),
            )
        )

    return registry


def engine_registry_from_deployments(
    deployments: DeploymentRegistry,
) -> EngineRegistry:
    registry = EngineRegistry()
    for deployment in deployments.all():
        registry.register(deployment.engine)
    return registry


def build_engine_registry(config: Settings = settings) -> EngineRegistry:
    """

    Build Ryuk's inference engine registry from application settings.

    Only engines explicitly enabled in configuration are registered.

    """

    return engine_registry_from_deployments(build_deployment_registry(config))
