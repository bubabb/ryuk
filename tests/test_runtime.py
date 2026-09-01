import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from backend.inference.base import InferenceEngine, InferenceRequest, InferenceResponse
from backend.inference.contracts import AttemptOutcome, ExecutionAttempt
from backend.inference.deployment import DeploymentRef, ModelRef
from backend.inference.registry import DeploymentRegistry, RegisteredDeployment
from backend.inference.runtime import (
    AdmissionState,
    CapacityState,
    DeploymentRuntimeState,
    Liveness,
    Readiness,
    RuntimeStateCollector,
    RuntimeStateStore,
)


@dataclass
class ProbeEngine(InferenceEngine):
    name: str
    delay: float
    available: bool

    async def is_available(self) -> bool:
        await asyncio.sleep(self.delay)
        return self.available

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        raise AssertionError("not used")


def registry(*engines: ProbeEngine) -> DeploymentRegistry:
    result = DeploymentRegistry()
    for engine in engines:
        result.register(
            RegisteredDeployment(
                ref=DeploymentRef(
                    deployment_id=engine.name,
                    model=ModelRef(f"model/{engine.name}"),
                    engine_name=engine.name,
                    endpoint_id=engine.name,
                ),
                engine=engine,
            )
        )
    return result


@pytest.mark.asyncio
async def test_collector_probes_concurrently_and_bounds_slow_engine() -> None:
    collector = RuntimeStateCollector(
        registry(
            ProbeEngine("fast", 0.0, True),
            ProbeEngine("slow", 1.0, True),
        ),
        probe_timeout=0.01,
        ttl_seconds=10,
    )

    await collector.refresh()

    assert collector.store.get("fast").readiness is Readiness.READY
    slow = collector.store.get("slow")
    assert slow.readiness is Readiness.NOT_READY
    assert slow.probe_error == "TimeoutError"


def test_stale_and_unknown_runtime_state_are_not_routable() -> None:
    now = datetime.now(UTC)
    unknown = DeploymentRuntimeState("unknown")
    stale = DeploymentRuntimeState(
        "stale",
        liveness=Liveness.UP,
        readiness=Readiness.READY,
        admission=AdmissionState.ACCEPTING,
        observed_at=now - timedelta(seconds=2),
        expires_at=now - timedelta(seconds=1),
    )

    assert unknown.is_routable(now) is False
    assert stale.is_stale(now) is True
    assert stale.is_routable(now) is False


def test_attempt_feedback_updates_runtime_summary() -> None:
    store = RuntimeStateStore(("deployment",))
    now = datetime.now(UTC)
    store.record_attempt(
        ExecutionAttempt(
            attempt_id="attempt-1",
            sequence=1,
            deployment_id="deployment",
            started_at=now,
            finished_at=now,
            duration_ms=12.0,
            outcome=AttemptOutcome.FAILED,
            failure_code="capacity_exceeded",
            retry_classification="other_deployment",
        )
    )

    summary = store.get("deployment").summary
    assert summary.attempt_count == 1
    assert summary.failure_count == 1
    assert summary.recent_failure_rate == 1.0
    assert summary.last_attempt_latency_ms == 12.0
    assert summary.last_failure_code == "capacity_exceeded"
    state = store.get("deployment")
    assert state.capacity is CapacityState.EXHAUSTED
    assert state.admission is AdmissionState.REJECTING
