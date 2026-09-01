from __future__ import annotations

import asyncio
import time
from collections.abc import Set
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from backend.inference.base import (
    DeploymentProvenance,
    InferenceEngine,
    InferenceRequest,
    InferenceResponse,
)
from backend.inference.capabilities import evaluate_capabilities
from backend.inference.compat import task_to_legacy_request
from backend.inference.contracts import (
    AdapterInferenceResult,
    AttemptOutcome,
    ExecutionAttempt,
    FinishReason,
    InferenceResult,
    InferenceTask,
    InferenceTiming,
    RoutingDecision,
    TextOutput,
    TokenUsage,
    TypedInferenceEngine,
)
from backend.inference.deployment import IdentityAssessment
from backend.inference.errors import (
    CancelledFailure,
    CapabilityMismatchFailure,
    DeadlineExceededFailure,
    DeploymentUnavailableFailure,
    IdentityMismatchFailure,
    InferenceFailure,
    RetryClassification,
    UnknownEnginePreferenceFailure,
)
from backend.inference.policy import PolicyCandidate, PolicyRuntime, rank_candidates
from backend.inference.registry import (
    DeploymentRegistry,
    EngineRegistry,
    RegisteredDeployment,
)
from backend.inference.runtime import CapacityState, RuntimeStateStore


class NoAvailableEngineError(DeploymentUnavailableFailure):
    """Raised when Ryuk cannot find an available inference deployment."""


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    max_attempts: int = 3
    default_deadline_seconds: float = 120.0
    backoff_seconds: tuple[float, ...] = (0.0,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        if self.default_deadline_seconds <= 0:
            raise ValueError("default_deadline_seconds must be positive.")
        if any(delay < 0 for delay in self.backoff_seconds):
            raise ValueError("backoff_seconds cannot contain negative values.")


class InferenceRouter:
    """Select a deployment and normalize typed results and provenance."""

    def __init__(
        self,
        registry: EngineRegistry | DeploymentRegistry,
        *,
        policy: ExecutionPolicy | None = None,
        circuit_open_deployment_ids: Set[str] = frozenset(),
        runtime_states: RuntimeStateStore | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self.circuit_open_deployment_ids = frozenset(circuit_open_deployment_ids)
        self.runtime_states = runtime_states

    async def select_deployment(
        self,
        preferred_engine: str | None = None,
    ) -> RegisteredDeployment:
        if not isinstance(self.registry, DeploymentRegistry):
            raise TypeError("Deployment selection requires a DeploymentRegistry.")

        if preferred_engine is not None:
            preferred = [
                deployment
                for deployment in self.registry.all()
                if deployment.engine.name.lower() == preferred_engine.lower()
            ]
            if not preferred:
                available = (
                    ", ".join(
                        sorted({item.engine.name for item in self.registry.all()})
                    )
                    or "none"
                )
                raise UnknownEnginePreferenceFailure(
                    context={
                        "preferred_engine": preferred_engine,
                        "registered_engines": available,
                    }
                )
            for deployment in preferred:
                if await self._deployment_available(deployment):
                    return deployment

        for deployment in self.registry.all():
            if (
                preferred_engine
                and deployment.engine.name.lower() == preferred_engine.lower()
            ):
                continue
            if await self._deployment_available(deployment):
                return deployment

        raise NoAvailableEngineError()

    async def _deployment_available(self, deployment: RegisteredDeployment) -> bool:
        if self.runtime_states is not None:
            return self.runtime_states.get(deployment.ref.deployment_id).is_routable()
        return await deployment.engine.is_available()

    async def select_engine(
        self,
        preferred_engine: str | None = None,
    ) -> InferenceEngine:
        if isinstance(self.registry, DeploymentRegistry):
            return (await self.select_deployment(preferred_engine)).engine

        if preferred_engine is not None:
            try:
                engine = self.registry.get(preferred_engine)
            except KeyError as exc:
                raise UnknownEnginePreferenceFailure(
                    context={"preferred_engine": preferred_engine}
                ) from exc
            if await engine.is_available():
                return engine

        for engine in self.registry.all():
            if preferred_engine and engine.name.lower() == preferred_engine.lower():
                continue
            if await engine.is_available():
                return engine

        raise NoAvailableEngineError()

    async def generate_task(
        self,
        task: InferenceTask,
        preferred_engine: str | None = None,
    ) -> InferenceResult:
        if not isinstance(self.registry, DeploymentRegistry):
            raise TypeError("Typed task execution requires a DeploymentRegistry.")

        deployments, routing_decision = self._ordered_deployments(
            task, preferred_engine
        )
        attempts: list[ExecutionAttempt] = []
        monotonic_deadline = self._monotonic_deadline(task)
        deployment_index = 0
        last_failure: InferenceFailure | None = None

        while (
            deployment_index < len(deployments)
            and len(attempts) < self.policy.max_attempts
        ):
            deployment = deployments[deployment_index]
            if deployment.ref.deployment_id in self.circuit_open_deployment_ids:
                deployment_index += 1
                continue
            if self.runtime_states is not None:
                if not self.runtime_states.get(
                    deployment.ref.deployment_id
                ).is_routable():
                    deployment_index += 1
                    continue
                available = True
            else:
                remaining = self._remaining(monotonic_deadline)
                if remaining is not None and remaining <= 0:
                    deadline = self._terminal_deadline(attempts)
                    deadline.context["routing_decision"] = routing_decision
                    raise deadline
                try:
                    available = await self._within_budget(
                        deployment.engine.is_available(), remaining
                    )
                except TimeoutError as exc:
                    deadline = self._terminal_deadline(attempts)
                    deadline.context["routing_decision"] = routing_decision
                    raise deadline from exc
            if not available:
                deployment_index += 1
                continue

            attempt_id = str(uuid4())
            sequence = len(attempts) + 1
            started_at = datetime.now(UTC)
            started = time.monotonic()
            try:
                remaining = self._remaining(monotonic_deadline)
                adapter_result, identity = await self._within_budget(
                    self._execute_task(deployment, task), remaining
                )
            except TimeoutError as exc:
                deadline_failure = DeadlineExceededFailure(
                    deployment_id=deployment.ref.deployment_id,
                    attempt_id=attempt_id,
                )
                attempts.append(
                    self._failed_attempt(
                        attempt_id,
                        sequence,
                        deployment,
                        started_at,
                        started,
                        deadline_failure,
                    )
                )
                self._record_attempt(attempts[-1])
                deadline_failure.context["execution_attempts"] = tuple(attempts)
                deadline_failure.context["routing_decision"] = routing_decision
                raise deadline_failure from exc
            except asyncio.CancelledError as exc:
                cancelled_failure = CancelledFailure(
                    deployment_id=deployment.ref.deployment_id,
                    attempt_id=attempt_id,
                )
                attempts.append(
                    self._failed_attempt(
                        attempt_id,
                        sequence,
                        deployment,
                        started_at,
                        started,
                        cancelled_failure,
                    )
                )
                self._record_attempt(attempts[-1])
                cancelled_failure.context["execution_attempts"] = tuple(attempts)
                cancelled_failure.context["routing_decision"] = routing_decision
                raise cancelled_failure from exc
            except InferenceFailure as failure:
                last_failure = failure
                failure.deployment_id = (
                    failure.deployment_id or deployment.ref.deployment_id
                )
                failure.attempt_id = failure.attempt_id or attempt_id
                attempts.append(
                    self._failed_attempt(
                        attempt_id, sequence, deployment, started_at, started, failure
                    )
                )
                self._record_attempt(attempts[-1])
                if failure.retry is RetryClassification.SAME_DEPLOYMENT:
                    await self._backoff(attempts, monotonic_deadline, routing_decision)
                    continue
                if failure.retry is RetryClassification.OTHER_DEPLOYMENT:
                    deployment_index += 1
                    await self._backoff(attempts, monotonic_deadline, routing_decision)
                    continue
                failure.context["execution_attempts"] = tuple(attempts)
                failure.context["routing_decision"] = routing_decision
                raise

            attempts.append(
                ExecutionAttempt(
                    attempt_id=attempt_id,
                    sequence=sequence,
                    deployment_id=deployment.ref.deployment_id,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    duration_ms=(time.monotonic() - started) * 1000,
                    outcome=AttemptOutcome.SUCCEEDED,
                )
            )
            self._record_attempt(attempts[-1])
            return InferenceResult(
                output=adapter_result.output,
                finish_reason=adapter_result.finish_reason,
                usage=adapter_result.usage,
                timing=adapter_result.timing,
                provenance=self._build_provenance(deployment, identity),
                adapter_metadata=adapter_result.adapter_metadata,
                attempts=tuple(attempts),
                routing_decision=routing_decision,
            )

        terminal_failure = last_failure or NoAvailableEngineError()
        terminal_failure.context["execution_attempts"] = tuple(attempts)
        terminal_failure.context["routing_decision"] = routing_decision
        raise terminal_failure

    def _record_attempt(self, attempt: ExecutionAttempt) -> None:
        if self.runtime_states is not None:
            self.runtime_states.record_attempt(attempt)

    def _ordered_deployments(
        self, task: InferenceTask, preferred_engine: str | None
    ) -> tuple[list[RegisteredDeployment], RoutingDecision]:
        assert isinstance(self.registry, DeploymentRegistry)
        deployments = list(self.registry.all())
        if preferred_engine is not None:
            preferred = [
                item
                for item in deployments
                if item.engine.name.lower() == preferred_engine.lower()
            ]
            if not preferred:
                raise UnknownEnginePreferenceFailure(
                    context={"preferred_engine": preferred_engine}
                )
            deployments = preferred + [
                item for item in deployments if item not in preferred
            ]

        eligible: list[RegisteredDeployment] = []
        public_rejections: list[dict[str, str]] = []
        decisions: dict[str, object] = {}
        for deployment in deployments:
            decision = evaluate_capabilities(task, deployment.capabilities)
            decisions[deployment.ref.deployment_id] = decision
            if decision.eligible:
                eligible.append(deployment)
            else:
                for rejection in decision.rejections:
                    public_rejections.append(
                        {
                            "deployment_id": deployment.ref.deployment_id,
                            **rejection.public_dict(),
                        }
                    )
        if not eligible:
            raise CapabilityMismatchFailure(
                context={
                    "rejections": public_rejections,
                    "eligibility_decisions": decisions,
                }
            )
        policy_candidates: list[PolicyCandidate] = []
        for index, deployment in enumerate(eligible):
            state = (
                self.runtime_states.get(deployment.ref.deployment_id)
                if self.runtime_states is not None
                else None
            )
            policy_runtime = (
                PolicyRuntime(
                    routable=state.is_routable(),
                    fresh=not state.is_stale(),
                    recent_failure_rate=state.summary.recent_failure_rate,
                    capacity_available=state.capacity is CapacityState.AVAILABLE,
                )
                if state is not None
                else None
            )
            policy_candidates.append(
                PolicyCandidate(
                    deployment_id=deployment.ref.deployment_id,
                    engine_name=deployment.engine.name,
                    registration_index=index,
                    capabilities=deployment.capabilities,
                    profile=deployment.policy_profile,
                    runtime=policy_runtime,
                )
            )
        routing_decision = rank_candidates(task, policy_candidates, preferred_engine)
        by_id = {item.ref.deployment_id: item for item in eligible}
        ordered = [
            by_id[deployment_id]
            for deployment_id in routing_decision.ordered_deployment_ids
        ]
        return ordered, routing_decision

    async def _execute_task(
        self, deployment: RegisteredDeployment, task: InferenceTask
    ) -> tuple[AdapterInferenceResult, IdentityAssessment]:
        inspection = await deployment.inspect_identity()
        if inspection.assessment.status.value == "mismatch":
            raise IdentityMismatchFailure(
                deployment_id=deployment.ref.deployment_id,
                context={"mismatched_fields": inspection.assessment.mismatched_fields},
            )
        if isinstance(deployment.engine, TypedInferenceEngine):
            result = await deployment.engine.generate_task(task)
        else:
            legacy_response = await deployment.engine.generate(
                task_to_legacy_request(task)
            )
            result = self._normalize_legacy_response(legacy_response)
        return result, inspection.assessment

    @staticmethod
    async def _within_budget(awaitable, remaining: float | None):
        if remaining is None:
            return await awaitable
        return await asyncio.wait_for(awaitable, timeout=max(remaining, 0.0))

    def _monotonic_deadline(self, task: InferenceTask) -> float:
        if task.deadline_at is None:
            return time.monotonic() + self.policy.default_deadline_seconds
        wall_remaining = (task.deadline_at - datetime.now(UTC)).total_seconds()
        return time.monotonic() + max(wall_remaining, 0.0)

    @staticmethod
    def _remaining(deadline: float | None) -> float | None:
        return None if deadline is None else deadline - time.monotonic()

    async def _backoff(
        self,
        attempts: list[ExecutionAttempt],
        deadline: float | None,
        routing_decision: RoutingDecision,
    ) -> None:
        if not self.policy.backoff_seconds:
            return
        delay = self.policy.backoff_seconds[
            min(len(attempts) - 1, len(self.policy.backoff_seconds) - 1)
        ]
        remaining = self._remaining(deadline)
        if remaining is not None and delay >= remaining:
            failure = self._terminal_deadline(attempts)
            failure.context["routing_decision"] = routing_decision
            raise failure
        if delay:
            await asyncio.sleep(delay)

    @staticmethod
    def _failed_attempt(
        attempt_id: str,
        sequence: int,
        deployment: RegisteredDeployment,
        started_at: datetime,
        started: float,
        failure: InferenceFailure,
    ) -> ExecutionAttempt:
        return ExecutionAttempt(
            attempt_id=attempt_id,
            sequence=sequence,
            deployment_id=deployment.ref.deployment_id,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            duration_ms=(time.monotonic() - started) * 1000,
            outcome=AttemptOutcome.FAILED,
            failure_code=failure.code,
            retry_classification=failure.retry,
        )

    @staticmethod
    def _terminal_deadline(attempts: list[ExecutionAttempt]) -> DeadlineExceededFailure:
        return DeadlineExceededFailure(context={"execution_attempts": tuple(attempts)})

    async def generate(
        self,
        request: InferenceRequest | InferenceTask,
        preferred_engine: str | None = None,
    ) -> InferenceResponse:
        if isinstance(request, InferenceTask):
            result = await self.generate_task(request, preferred_engine)
            return self._typed_to_legacy_response(result)

        if isinstance(self.registry, DeploymentRegistry):
            deployment = await self.select_deployment(preferred_engine)
            inspection = await deployment.inspect_identity()
            legacy_response = await deployment.engine.generate(request)
            adapter_result = self._normalize_legacy_response(legacy_response)
            result = InferenceResult(
                output=adapter_result.output,
                finish_reason=adapter_result.finish_reason,
                usage=adapter_result.usage,
                timing=adapter_result.timing,
                provenance=self._build_provenance(
                    deployment,
                    inspection.assessment,
                ),
                adapter_metadata=adapter_result.adapter_metadata,
            )
            return self._typed_to_legacy_response(result)

        engine = await self.select_engine(preferred_engine)
        return await engine.generate(request)

    @staticmethod
    def _normalize_legacy_response(
        response: InferenceResponse,
    ) -> AdapterInferenceResult:
        adapter_finish_reason = response.metadata.get("sglang_finish_reason")
        finish_reasons = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "cancelled": FinishReason.CANCELLED,
            "abort": FinishReason.CANCELLED,
        }
        finish_reason = (
            finish_reasons.get(adapter_finish_reason, FinishReason.UNKNOWN)
            if isinstance(adapter_finish_reason, str)
            else FinishReason.UNKNOWN
        )
        return AdapterInferenceResult(
            output=TextOutput(response.text),
            finish_reason=finish_reason,
            usage=TokenUsage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            ),
            timing=InferenceTiming(total_ms=response.latency_ms),
            adapter_metadata=response.metadata,
        )

    @staticmethod
    def _build_provenance(
        deployment: RegisteredDeployment,
        identity: IdentityAssessment,
    ) -> DeploymentProvenance:
        observed_model = (
            identity.observed.model if identity.observed is not None else None
        )
        effective_model = observed_model or deployment.ref.model
        return DeploymentProvenance(
            deployment_id=deployment.ref.deployment_id,
            engine_name=deployment.ref.engine_name,
            engine_version=deployment.ref.engine_version,
            serving_runtime=deployment.ref.serving_runtime,
            model_artifact_id=(
                effective_model.artifact_id if effective_model is not None else None
            ),
            model_revision=(
                effective_model.revision if effective_model is not None else None
            ),
            model_verification=identity.status,
        )

    @staticmethod
    def _typed_to_legacy_response(result: InferenceResult) -> InferenceResponse:
        return InferenceResponse(
            text=result.output.text,
            model=result.provenance.model_artifact_id,
            engine=result.provenance.engine_name,
            latency_ms=result.timing.total_ms,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            metadata=result.adapter_metadata,
            provenance=result.provenance,
        )
