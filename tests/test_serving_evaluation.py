import pytest

from backend.evaluation.serving import (
    DecisionStatus,
    ServingBenchmark,
    evaluate_candidate,
)


def benchmark(
    candidate: str, *, throughput: float, ttft: float = 100
) -> ServingBenchmark:
    return ServingBenchmark(
        candidate=candidate,
        workload_id="prefix-heavy-v1",
        hardware_id="8xh100-image-digest",
        successful_requests=100,
        failed_requests=0,
        ttft_p95_ms=ttft,
        inter_token_p95_ms=12,
        output_tokens_per_second=throughput,
        recovery_seconds=4,
        kv_reuse_ratio=0.5,
    )


def test_measured_gain_can_pass_adoption_gate() -> None:
    decision = evaluate_candidate(
        benchmark("direct", throughput=100), benchmark("dynamo", throughput=115)
    )
    assert decision.status is DecisionStatus.ADOPT


def test_insufficient_gain_and_ttft_regression_hold_adoption() -> None:
    decision = evaluate_candidate(
        benchmark("direct", throughput=100),
        benchmark("trtllm", throughput=105, ttft=110),
    )
    assert decision.status is DecisionStatus.HOLD
    assert "insufficient_throughput_gain" in decision.reasons
    assert "ttft_regression" in decision.reasons


def test_invalid_benchmark_is_rejected() -> None:
    with pytest.raises(ValueError):
        benchmark("direct", throughput=-1)
