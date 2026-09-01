from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from backend.inference.contracts import AttemptOutcome, ExecutionAttempt
from backend.inference.registry import DeploymentRegistry


class Liveness(StrEnum):
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"


class Readiness(StrEnum):
    UNKNOWN = "unknown"
    READY = "ready"
    NOT_READY = "not_ready"


class AdmissionState(StrEnum):
    UNKNOWN = "unknown"
    ACCEPTING = "accepting"
    REJECTING = "rejecting"


class CapacityState(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class RuntimeSummary:
    attempt_count: int = 0
    failure_count: int = 0
    recent_failure_rate: float | None = None
    last_attempt_latency_ms: float | None = None
    last_failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class DeploymentRuntimeState:
    deployment_id: str
    liveness: Liveness = Liveness.UNKNOWN
    readiness: Readiness = Readiness.UNKNOWN
    admission: AdmissionState = AdmissionState.UNKNOWN
    capacity: CapacityState = CapacityState.UNKNOWN
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    probe_latency_ms: float | None = None
    probe_error: str | None = None
    summary: RuntimeSummary = RuntimeSummary()

    def is_stale(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.expires_at is None or self.expires_at <= current

    def is_routable(self, now: datetime | None = None) -> bool:
        return (
            not self.is_stale(now)
            and self.liveness is Liveness.UP
            and self.readiness is Readiness.READY
            and self.admission is AdmissionState.ACCEPTING
            and self.capacity is not CapacityState.EXHAUSTED
        )


class RuntimeStateStore:
    def __init__(self, deployment_ids: tuple[str, ...]) -> None:
        self._states = {
            deployment_id: DeploymentRuntimeState(deployment_id)
            for deployment_id in deployment_ids
        }
        self._attempt_history: dict[str, list[bool]] = {
            deployment_id: [] for deployment_id in deployment_ids
        }

    def get(self, deployment_id: str) -> DeploymentRuntimeState:
        return self._states.get(deployment_id, DeploymentRuntimeState(deployment_id))

    def all(self) -> tuple[DeploymentRuntimeState, ...]:
        return tuple(self._states.values())

    def put(self, state: DeploymentRuntimeState) -> None:
        self._states[state.deployment_id] = state

    def record_attempt(self, attempt: ExecutionAttempt) -> None:
        state = self.get(attempt.deployment_id)
        history = self._attempt_history.setdefault(attempt.deployment_id, [])
        history.append(attempt.outcome is AttemptOutcome.FAILED)
        del history[:-20]
        attempts = len(history)
        failed = sum(history)
        liveness = state.liveness
        readiness = state.readiness
        admission = state.admission
        capacity = state.capacity
        if attempt.outcome is AttemptOutcome.SUCCEEDED:
            admission = AdmissionState.ACCEPTING
            capacity = CapacityState.AVAILABLE
        elif attempt.failure_code == "capacity_exceeded":
            admission = AdmissionState.REJECTING
            capacity = CapacityState.EXHAUSTED
        elif attempt.failure_code == "deployment_unavailable":
            liveness = Liveness.DOWN
            readiness = Readiness.NOT_READY
            admission = AdmissionState.REJECTING
        self.put(
            replace(
                state,
                liveness=liveness,
                readiness=readiness,
                admission=admission,
                capacity=capacity,
                summary=RuntimeSummary(
                    attempt_count=attempts,
                    failure_count=failed,
                    recent_failure_rate=failed / attempts,
                    last_attempt_latency_ms=attempt.duration_ms,
                    last_failure_code=(
                        attempt.failure_code
                        if attempt.outcome is AttemptOutcome.FAILED
                        else None
                    ),
                ),
            )
        )


class RuntimeStateCollector:
    def __init__(
        self,
        registry: DeploymentRegistry,
        *,
        probe_timeout: float = 3.0,
        ttl_seconds: float = 15.0,
        interval_seconds: float = 5.0,
    ) -> None:
        self.registry = registry
        self.store = RuntimeStateStore(registry.ids())
        self.probe_timeout = probe_timeout
        self.ttl_seconds = ttl_seconds
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        now = datetime.now(UTC)
        for deployment in registry.all():
            if deployment.ref.serving_runtime == "in_process":
                self.store.put(
                    DeploymentRuntimeState(
                        deployment_id=deployment.ref.deployment_id,
                        liveness=Liveness.UP,
                        readiness=Readiness.READY,
                        admission=AdmissionState.ACCEPTING,
                        observed_at=now,
                        expires_at=now + timedelta(seconds=ttl_seconds),
                    )
                )

    async def refresh(self) -> None:
        await asyncio.gather(
            *(
                self._probe(
                    deployment.ref.deployment_id, deployment.engine.is_available()
                )
                for deployment in self.registry.all()
            )
        )

    async def _probe(self, deployment_id: str, availability: Awaitable[bool]) -> None:
        started = time.monotonic()
        observed_at = datetime.now(UTC)
        try:
            available = await asyncio.wait_for(availability, timeout=self.probe_timeout)
            error = None
        except Exception as exc:
            available = False
            error = type(exc).__name__
        previous = self.store.get(deployment_id)
        self.store.put(
            DeploymentRuntimeState(
                deployment_id=deployment_id,
                liveness=Liveness.UP if available else Liveness.DOWN,
                readiness=Readiness.READY if available else Readiness.NOT_READY,
                admission=(
                    AdmissionState.ACCEPTING if available else AdmissionState.REJECTING
                ),
                capacity=CapacityState.UNKNOWN,
                observed_at=observed_at,
                expires_at=observed_at + timedelta(seconds=self.ttl_seconds),
                probe_latency_ms=(time.monotonic() - started) * 1000,
                probe_error=error,
                summary=previous.summary,
            )
        )

    async def start(self) -> None:
        await self.refresh()
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self.refresh()

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
