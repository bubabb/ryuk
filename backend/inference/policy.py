from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.inference.capabilities import DeploymentCapabilities, TaskKind
from backend.inference.contracts import (
    InferenceTask,
    RoutingDecision,
    RoutingScore,
    TextInput,
)

POLICY_VERSION = "ryuk-deterministic-v1"


class CostClass(StrEnum):
    UNKNOWN = "unknown"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LatencyClass(StrEnum):
    UNKNOWN = "unknown"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class RoutingPolicyProfile:
    cost_class: CostClass = CostClass.UNKNOWN
    latency_class: LatencyClass = LatencyClass.UNKNOWN
    text_suitability: int = 0
    chat_suitability: int = 0

    def __post_init__(self) -> None:
        for value in (self.text_suitability, self.chat_suitability):
            if not -10 <= value <= 10:
                raise ValueError("Suitability must be between -10 and 10.")


@dataclass(frozen=True, slots=True)
class PolicyCandidate:
    deployment_id: str
    engine_name: str
    registration_index: int
    capabilities: DeploymentCapabilities
    profile: RoutingPolicyProfile
    runtime: PolicyRuntime | None = None


@dataclass(frozen=True, slots=True)
class PolicyRuntime:
    routable: bool
    fresh: bool = False
    recent_failure_rate: float | None = None
    capacity_available: bool = False


def rank_candidates(
    task: InferenceTask,
    candidates: list[PolicyCandidate],
    preferred_engine: str | None,
) -> RoutingDecision:
    scored = [_score(task, candidate, preferred_engine) for candidate in candidates]
    by_id = {candidate.deployment_id: candidate for candidate in candidates}
    scored.sort(
        key=lambda score: (-score.total, by_id[score.deployment_id].registration_index)
    )
    return RoutingDecision(
        policy_version=POLICY_VERSION,
        ordered_deployment_ids=tuple(score.deployment_id for score in scored),
        candidates=tuple(scored),
    )


def _score(
    task: InferenceTask, candidate: PolicyCandidate, preferred_engine: str | None
) -> RoutingScore:
    components: list[tuple[str, int]] = []
    explanations: list[str] = []

    preferred = (
        100
        if (
            preferred_engine is not None
            and candidate.engine_name.lower() == preferred_engine.lower()
        )
        else 0
    )
    _add(components, explanations, "preference", preferred)

    runtime = candidate.runtime
    readiness = 20 if runtime is not None and runtime.routable else 0
    _add(components, explanations, "readiness", readiness)
    freshness = 5 if runtime is not None and runtime.fresh else 0
    _add(components, explanations, "freshness", freshness)
    failure = 0
    if runtime is not None and runtime.recent_failure_rate is not None:
        failure = round(20 * (1 - runtime.recent_failure_rate))
    _add(components, explanations, "reliability", failure)
    capacity = 10 if runtime is not None and runtime.capacity_available else 0
    _add(components, explanations, "capacity", capacity)

    context = _context_score(task, candidate.capabilities)
    _add(components, explanations, "context_headroom", context)
    _add(
        components,
        explanations,
        "cost",
        {CostClass.LOW: 10, CostClass.MEDIUM: 5}.get(candidate.profile.cost_class, 0),
    )
    _add(
        components,
        explanations,
        "latency",
        {LatencyClass.LOW: 10, LatencyClass.MEDIUM: 5}.get(
            candidate.profile.latency_class, 0
        ),
    )
    kind = TaskKind.TEXT if isinstance(task.input, TextInput) else TaskKind.CHAT
    suitability = (
        candidate.profile.text_suitability
        if kind is TaskKind.TEXT
        else candidate.profile.chat_suitability
    )
    _add(components, explanations, "task_suitability", suitability)
    return RoutingScore(
        deployment_id=candidate.deployment_id,
        total=sum(value for _, value in components),
        components=tuple(components),
        explanation=tuple(explanations),
    )


def _context_score(task: InferenceTask, capabilities: DeploymentCapabilities) -> int:
    required = task.requirements.required_context_tokens
    claim = capabilities.max_context_tokens
    if required is None or claim is None:
        return 0
    return 10 if claim.value >= required * 2 else 5


def _add(
    components: list[tuple[str, int]], explanations: list[str], name: str, value: int
) -> None:
    components.append((name, value))
    explanations.append(f"{name}={value}")
