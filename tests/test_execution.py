import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from backend.inference.base import InferenceEngine, InferenceRequest, InferenceResponse
from backend.inference.capabilities import (
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
)
from backend.inference.contracts import (
    AdapterInferenceResult,
    AttemptOutcome,
    FinishReason,
    GenerationConfig,
    InferenceTask,
    InferenceTiming,
    TaskRequirements,
    TextInput,
    TextOutput,
    TokenUsage,
    TraceContext,
)
from backend.inference.deployment import DeploymentRef, ModelRef
from backend.inference.errors import (
    DeadlineExceededFailure,
    GenerationFailure,
    InferenceFailure,
    RetryClassification,
)
from backend.inference.registry import DeploymentRegistry, RegisteredDeployment
from backend.inference.router import ExecutionPolicy, InferenceRouter


@dataclass
class ControlledEngine(InferenceEngine):
    name: str
    failure: bool = False
    delay: float = 0.0
    calls: int = 0

    async def is_available(self) -> bool:
        return True

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        raise AssertionError("typed execution expected")

    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.failure:
            raise GenerationFailure(context={"engine": self.name})
        return AdapterInferenceResult(
            output=TextOutput(f"{self.name}: ok"),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(),
            timing=InferenceTiming(),
            adapter_metadata={},
        )


class SameDeploymentRetryFailure(InferenceFailure):
    code = "same_deployment_retry"
    retry = RetryClassification.SAME_DEPLOYMENT


@dataclass
class FlakyEngine(ControlledEngine):
    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult:
        if self.calls == 0:
            self.calls += 1
            raise SameDeploymentRetryFailure()
        return await super().generate_task(task)


def task(*, deadline_ms: float | None = None) -> InferenceTask:
    deadline = (
        datetime.now(UTC) + timedelta(milliseconds=deadline_ms)
        if deadline_ms is not None
        else None
    )
    return InferenceTask(
        input=TextInput("hello"),
        generation=GenerationConfig(),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
        deadline_at=deadline,
    )


def registry(*engines: ControlledEngine) -> DeploymentRegistry:
    deployments = DeploymentRegistry()
    for engine in engines:
        deployments.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=f"{engine.name}-deployment",
                    model=ModelRef(f"model/{engine.name}"),
                    engine_name=engine.name,
                    endpoint_id=f"{engine.name}-endpoint",
                ),
                engine=engine,
                capabilities=DeploymentCapabilities(
                    task_kinds=configured_claim(frozenset({TaskKind.TEXT}), "test")
                ),
            )
        )
    return deployments


@pytest.mark.asyncio
async def test_generation_failure_fails_over_with_replayable_attempts() -> None:
    first = ControlledEngine("first", failure=True)
    second = ControlledEngine("second")

    result = await InferenceRouter(registry(first, second)).generate_task(task())

    assert result.output.text == "second: ok"
    assert [attempt.deployment_id for attempt in result.attempts] == [
        "first-deployment",
        "second-deployment",
    ]
    assert [attempt.outcome for attempt in result.attempts] == [
        AttemptOutcome.FAILED,
        AttemptOutcome.SUCCEEDED,
    ]
    assert result.attempts[0].failure_code == "generation_failure"


@pytest.mark.asyncio
async def test_deadline_bounds_in_flight_attempt_and_records_failure() -> None:
    slow = ControlledEngine("slow", delay=0.2)

    with pytest.raises(DeadlineExceededFailure) as raised:
        await InferenceRouter(registry(slow)).generate_task(task(deadline_ms=10))

    attempts = raised.value.context["execution_attempts"]
    assert len(attempts) == 1
    assert attempts[0].failure_code == "deadline_exceeded"
    assert slow.calls == 1


@pytest.mark.asyncio
async def test_max_attempts_prevents_retry_storm() -> None:
    first = ControlledEngine("first", failure=True)
    second = ControlledEngine("second")
    router = InferenceRouter(
        registry(first, second), policy=ExecutionPolicy(max_attempts=1)
    )

    with pytest.raises(GenerationFailure) as raised:
        await router.generate_task(task())

    assert first.calls == 1
    assert second.calls == 0
    assert len(raised.value.context["execution_attempts"]) == 1


@pytest.mark.asyncio
async def test_same_deployment_retries_only_when_classification_allows_it() -> None:
    engine = FlakyEngine("flaky")

    result = await InferenceRouter(registry(engine)).generate_task(task())

    assert engine.calls == 2
    assert [attempt.deployment_id for attempt in result.attempts] == [
        "flaky-deployment",
        "flaky-deployment",
    ]
    assert result.attempts[0].retry_classification == "same_deployment"


@pytest.mark.asyncio
async def test_circuit_open_deployment_is_skipped() -> None:
    first = ControlledEngine("first")
    second = ControlledEngine("second")
    router = InferenceRouter(
        registry(first, second),
        circuit_open_deployment_ids={"first-deployment"},
    )

    result = await router.generate_task(task())

    assert first.calls == 0
    assert second.calls == 1
    assert [attempt.deployment_id for attempt in result.attempts] == [
        "second-deployment"
    ]
