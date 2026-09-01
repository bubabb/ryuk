from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.inference.capabilities import (
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
    evaluate_capabilities,
)
from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceTask,
    RoutingRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.policy import (
    POLICY_VERSION,
    CostClass,
    LatencyClass,
    PolicyCandidate,
    PolicyRuntime,
    RoutingPolicyProfile,
    rank_candidates,
)


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    expected_eligible: tuple[str, ...]
    actual_eligible: tuple[str, ...]
    expected_selected: str | None
    selected: str | None
    attempt_plan: tuple[str, ...]
    completed: bool | None
    deadline_met: bool | None
    accepted_cost: float | None
    latency_ms: float | None
    failover_recovered: bool | None
    stable: bool
    counterfactual_selections: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    scenario_count: int
    eligibility_accuracy: float
    selection_accuracy: float | None
    constraint_violation_rate: float
    completion_success_rate: float | None
    deadline_success_rate: float | None
    average_cost_per_accepted_result: float | None
    average_latency_ms: float | None
    failover_recovery_rate: float | None
    decision_stability_rate: float
    outcome_coverage: float
    quality_label_coverage: float
    uncertainty_count: int


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    corpus_version: str
    policy_version: str
    metrics: EvaluationMetrics
    accepted: bool
    acceptance_failures: tuple[str, ...]
    scenarios: tuple[ScenarioResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_corpus(path: Path) -> EvaluationReport:
    corpus: dict[str, Any] = json.loads(path.read_text())
    if corpus["policy_version"] != POLICY_VERSION:
        raise ValueError("Corpus policy_version does not match the active policy.")
    results = tuple(_evaluate_scenario(item) for item in corpus["scenarios"])
    metrics = _metrics(results)
    failures = _acceptance_failures(metrics, corpus["thresholds"])
    return EvaluationReport(
        corpus_version=corpus["corpus_version"],
        policy_version=POLICY_VERSION,
        metrics=metrics,
        accepted=not failures,
        acceptance_failures=tuple(failures),
        scenarios=results,
    )


def _evaluate_scenario(data: dict[str, Any]) -> ScenarioResult:
    task = _task(data)
    all_candidates = [
        _candidate(item, index) for index, item in enumerate(data["candidates"])
    ]
    eligible = [
        candidate
        for candidate in all_candidates
        if evaluate_capabilities(task, candidate.capabilities).eligible
    ]
    decision = rank_candidates(task, eligible, data.get("preferred_engine"))
    selected = (
        decision.ordered_deployment_ids[0] if decision.ordered_deployment_ids else None
    )
    attempt_plan: list[str] = []
    completed: bool | None = None
    deadline_met: bool | None = None
    cost: float | None = None
    latency: float | None = None
    outcomes = {
        item["deployment_id"]: item.get("outcome") for item in data["candidates"]
    }
    for deployment_id in decision.ordered_deployment_ids:
        outcome = outcomes[deployment_id]
        if outcome is None:
            continue
        attempt_plan.append(deployment_id)
        if outcome["completed"]:
            completed = True
            deadline_met = outcome.get("deadline_met")
            cost = outcome.get("cost")
            latency = outcome.get("latency_ms")
            break
        completed = False
    recovered = completed is True if len(attempt_plan) > 1 else None
    replay = rank_candidates(
        task, list(reversed(eligible)), data.get("preferred_engine")
    )
    stable = replay.ordered_deployment_ids == decision.ordered_deployment_ids
    counterfactuals: list[tuple[str, str | None]] = []
    for removed in eligible:
        remaining = [item for item in eligible if item is not removed]
        replay_without = rank_candidates(task, remaining, data.get("preferred_engine"))
        alternate = (
            replay_without.ordered_deployment_ids[0]
            if replay_without.ordered_deployment_ids
            else None
        )
        counterfactuals.append((removed.deployment_id, alternate))
    return ScenarioResult(
        scenario_id=data["id"],
        expected_eligible=tuple(data["expected_eligible"]),
        actual_eligible=tuple(item.deployment_id for item in eligible),
        expected_selected=data.get("expected_selected"),
        selected=selected,
        attempt_plan=tuple(attempt_plan),
        completed=completed,
        deadline_met=deadline_met,
        accepted_cost=cost,
        latency_ms=latency,
        failover_recovered=recovered,
        stable=stable,
        counterfactual_selections=tuple(counterfactuals),
    )


def _task(data: dict[str, Any]) -> InferenceTask:
    task_data = data["task"]
    input_value: TextInput | ChatInput
    if task_data.get("kind", "text") == "chat":
        input_value = ChatInput(
            messages=(ChatMessage(ChatRole.USER, task_data.get("text", "hello")),)
        )
    else:
        input_value = TextInput(task_data.get("text", "hello"))
    requirements = task_data.get("requirements", {})
    return InferenceTask(
        input=input_value,
        generation=GenerationConfig(),
        requirements=RoutingRequirements(**requirements),
        trace=TraceContext(request_id=f"eval-{data['id']}"),
    )


def _candidate(data: dict[str, Any], index: int) -> PolicyCandidate:
    caps = data.get("capabilities", {})
    kinds = frozenset(TaskKind(item) for item in caps.get("task_kinds", []))
    capabilities = DeploymentCapabilities(
        task_kinds=configured_claim(kinds, "evaluation") if kinds else None,
        max_context_tokens=(
            configured_claim(caps["max_context_tokens"], "evaluation")
            if "max_context_tokens" in caps
            else None
        ),
        streaming=(
            configured_claim(caps["streaming"], "evaluation")
            if "streaming" in caps
            else None
        ),
        production_eligible=(
            configured_claim(caps["production_eligible"], "evaluation")
            if "production_eligible" in caps
            else None
        ),
    )
    profile = data.get("profile", {})
    runtime = data.get("runtime")
    return PolicyCandidate(
        deployment_id=data["deployment_id"],
        engine_name=data["engine_name"],
        registration_index=index,
        capabilities=capabilities,
        profile=RoutingPolicyProfile(
            cost_class=CostClass(profile.get("cost_class", "unknown")),
            latency_class=LatencyClass(profile.get("latency_class", "unknown")),
            text_suitability=profile.get("text_suitability", 0),
            chat_suitability=profile.get("chat_suitability", 0),
        ),
        runtime=(PolicyRuntime(**runtime) if runtime is not None else None),
    )


def _metrics(results: tuple[ScenarioResult, ...]) -> EvaluationMetrics:
    count = len(results)
    labeled_selection = [item for item in results if item.expected_selected is not None]
    completed = [item.completed for item in results if item.completed is not None]
    deadlines = [item.deadline_met for item in results if item.deadline_met is not None]
    recovered = [
        item.failover_recovered
        for item in results
        if item.failover_recovered is not None
    ]
    costs = [item.accepted_cost for item in results if item.accepted_cost is not None]
    latencies = [item.latency_ms for item in results if item.latency_ms is not None]
    violations = sum(
        item.selected is not None and item.selected not in item.actual_eligible
        for item in results
    )
    return EvaluationMetrics(
        scenario_count=count,
        eligibility_accuracy=sum(
            item.actual_eligible == item.expected_eligible for item in results
        )
        / count,
        selection_accuracy=(
            sum(item.selected == item.expected_selected for item in labeled_selection)
            / len(labeled_selection)
            if labeled_selection
            else None
        ),
        constraint_violation_rate=violations / count,
        completion_success_rate=_rate(completed),
        deadline_success_rate=_rate(deadlines),
        average_cost_per_accepted_result=_average(costs),
        average_latency_ms=_average(latencies),
        failover_recovery_rate=_rate(recovered),
        decision_stability_rate=sum(item.stable for item in results) / count,
        outcome_coverage=len(completed) / count,
        quality_label_coverage=0.0,
        uncertainty_count=sum(item.completed is None for item in results),
    )


def _rate(values: Sequence[bool]) -> float | None:
    return sum(value is True for value in values) / len(values) if values else None


def _average(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _acceptance_failures(
    metrics: EvaluationMetrics, thresholds: dict[str, dict[str, float]]
) -> list[str]:
    failures: list[str] = []
    for name, minimum in thresholds.get("minimum", {}).items():
        value = getattr(metrics, name)
        if value is None or value < minimum:
            failures.append(f"{name}={value} is below {minimum}")
    for name, maximum in thresholds.get("maximum", {}).items():
        value = getattr(metrics, name)
        if value is None or value > maximum:
            failures.append(f"{name}={value} is above {maximum}")
    return failures
