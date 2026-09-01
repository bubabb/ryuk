from dataclasses import dataclass

import pytest

from backend.config import AppEnvironment, Settings
from backend.inference.base import InferenceEngine, InferenceRequest, InferenceResponse
from backend.inference.capabilities import (
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
)
from backend.inference.compat import LegacyAdapterUnsupportedTaskError
from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.deployment import DeploymentRef, IdentityVerification, ModelRef
from backend.inference.errors import UnknownEnginePreferenceFailure
from backend.inference.registry import (
    DeploymentRegistry,
    EngineRegistry,
    RegisteredDeployment,
    build_deployment_registry,
)
from backend.inference.router import InferenceRouter, NoAvailableEngineError


@dataclass
class StubEngine(InferenceEngine):
    name: str
    available: bool

    async def is_available(self) -> bool:
        return self.available

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            text=f"{self.name}: {request.prompt}",
            model=request.model,
            engine=self.name,
        )


@pytest.mark.asyncio
async def test_selects_available_preferred_engine() -> None:
    registry = EngineRegistry()
    registry.register_many([StubEngine("first", True), StubEngine("preferred", True)])

    selected = await InferenceRouter(registry).select_engine("preferred")

    assert selected.name == "preferred"


@pytest.mark.asyncio
async def test_falls_back_when_preferred_engine_is_offline() -> None:
    registry = EngineRegistry()
    registry.register_many([StubEngine("sglang", False), StubEngine("mock", True)])
    request = InferenceRequest(prompt="hello", model="test-model")

    response = await InferenceRouter(registry).generate(
        request, preferred_engine="sglang"
    )

    assert response.engine == "mock"
    assert response.text == "mock: hello"


@pytest.mark.asyncio
async def test_unknown_preferred_engine_raises_typed_failure() -> None:
    router = InferenceRouter(EngineRegistry())

    with pytest.raises(UnknownEnginePreferenceFailure) as raised:
        await router.select_engine("missing")

    assert raised.value.code == "unknown_engine_preference"
    assert raised.value.context == {"preferred_engine": "missing"}


@pytest.mark.asyncio
async def test_no_available_engine_raises_controlled_error() -> None:
    registry = EngineRegistry()
    registry.register(StubEngine("offline", False))

    with pytest.raises(NoAvailableEngineError):
        await InferenceRouter(registry).select_engine()


@pytest.mark.asyncio
async def test_deployment_router_returns_verified_model_provenance() -> None:
    deployments = build_deployment_registry(
        Settings(
            app_env=AppEnvironment.TEST,
            sglang_enabled=False,
            mock_enabled=True,
        )
    )
    request = InferenceRequest(prompt="hello", model="caller-controlled-name")

    response = await InferenceRouter(deployments).generate(
        request,
        preferred_engine="mock",
    )

    assert response.model == "ryuk/mock"
    assert response.provenance is not None
    assert response.provenance.deployment_id == "mock-development"
    assert response.provenance.engine_name == "mock"
    assert response.provenance.model_artifact_id == "ryuk/mock"
    assert response.provenance.model_verification is IdentityVerification.VERIFIED


@pytest.mark.asyncio
async def test_mock_executes_typed_chat_natively() -> None:
    deployments = build_deployment_registry(
        Settings(
            app_env=AppEnvironment.TEST,
            sglang_enabled=False,
            mock_enabled=True,
        )
    )
    task = InferenceTask(
        input=ChatInput(messages=(ChatMessage(ChatRole.USER, "hello from chat"),)),
        generation=GenerationConfig(),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
    )

    result = await InferenceRouter(deployments).generate_task(task, "mock")

    assert result.output.text == "Mock chat response for: hello from chat"
    assert result.adapter_metadata["input_kind"] == "chat"
    assert result.provenance.model_verification is IdentityVerification.VERIFIED
    assert result.routing_decision is not None
    assert result.routing_decision.policy_version == "ryuk-deterministic-v1"
    assert result.routing_decision.ordered_deployment_ids == ("mock-development",)


@pytest.mark.asyncio
async def test_legacy_adapter_rejects_chat_without_flattening() -> None:
    deployments = DeploymentRegistry()
    deployments.register(
        RegisteredDeployment(
            ref=DeploymentRef(
                deployment_id="legacy",
                model=ModelRef("legacy/model"),
                engine_name="legacy",
                endpoint_id="legacy-endpoint",
            ),
            engine=StubEngine("legacy", True),
            capabilities=DeploymentCapabilities(
                task_kinds=configured_claim(
                    frozenset({TaskKind.TEXT, TaskKind.CHAT}), "test"
                )
            ),
        )
    )
    task = InferenceTask(
        input=ChatInput(messages=(ChatMessage(ChatRole.USER, "hello"),)),
        generation=GenerationConfig(),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
    )

    with pytest.raises(LegacyAdapterUnsupportedTaskError) as raised:
        await InferenceRouter(deployments).generate_task(task, "legacy")

    assert raised.value.code == "unsupported_task"


@pytest.mark.asyncio
async def test_legacy_text_result_is_normalized_to_typed_result() -> None:
    deployments = DeploymentRegistry()
    deployments.register(
        RegisteredDeployment(
            ref=DeploymentRef(
                deployment_id="legacy",
                model=ModelRef("legacy/model"),
                engine_name="legacy",
                endpoint_id="legacy-endpoint",
            ),
            engine=StubEngine("legacy", True),
            capabilities=DeploymentCapabilities(
                task_kinds=configured_claim(frozenset({TaskKind.TEXT}), "test")
            ),
        )
    )
    task = InferenceTask(
        input=TextInput("hello"),
        generation=GenerationConfig(),
        requirements=TaskRequirements(requested_model="legacy/model"),
        trace=TraceContext(request_id="request-1"),
    )

    result = await InferenceRouter(deployments).generate_task(task, "legacy")

    assert result.output.text == "legacy: hello"
    assert result.finish_reason.value == "unknown"
    assert result.provenance.model_artifact_id == "legacy/model"
