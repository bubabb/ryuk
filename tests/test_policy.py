from backend.inference.capabilities import DeploymentCapabilities
from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.policy import (
    CostClass,
    LatencyClass,
    PolicyCandidate,
    PolicyRuntime,
    RoutingPolicyProfile,
    rank_candidates,
)


def task() -> InferenceTask:
    return InferenceTask(
        input=TextInput("hello"),
        generation=GenerationConfig(),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
    )


def candidate(
    deployment_id: str,
    index: int,
    *,
    engine: str = "engine",
    profile: RoutingPolicyProfile | None = None,
    runtime: PolicyRuntime | None = None,
) -> PolicyCandidate:
    return PolicyCandidate(
        deployment_id=deployment_id,
        engine_name=engine,
        registration_index=index,
        capabilities=DeploymentCapabilities(),
        profile=profile or RoutingPolicyProfile(),
        runtime=runtime,
    )


def test_preference_is_explicit_and_explainable() -> None:
    decision = rank_candidates(
        task(),
        [candidate("first", 0), candidate("preferred", 1, engine="vllm")],
        "vllm",
    )

    assert decision.policy_version == "ryuk-deterministic-v1"
    assert decision.ordered_deployment_ids == ("preferred", "first")
    preferred = decision.candidates[0]
    assert dict(preferred.components)["preference"] == 100
    assert "preference=100" in preferred.explanation


def test_reliability_cost_and_latency_rank_deterministically() -> None:
    strong = candidate(
        "strong",
        1,
        profile=RoutingPolicyProfile(
            cost_class=CostClass.LOW,
            latency_class=LatencyClass.LOW,
            text_suitability=5,
        ),
        runtime=PolicyRuntime(
            routable=True, recent_failure_rate=0.0, capacity_available=True
        ),
    )
    weak = candidate(
        "weak",
        0,
        runtime=PolicyRuntime(
            routable=True, recent_failure_rate=1.0, capacity_available=False
        ),
    )

    decision = rank_candidates(task(), [weak, strong], None)

    assert decision.ordered_deployment_ids == ("strong", "weak")
    assert decision.candidates[0].total > decision.candidates[1].total


def test_equal_scores_preserve_registration_order() -> None:
    decision = rank_candidates(
        task(), [candidate("first", 0), candidate("second", 1)], None
    )
    assert decision.ordered_deployment_ids == ("first", "second")
