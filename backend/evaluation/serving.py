from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionStatus(StrEnum):
    ADOPT = "adopt"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class ServingBenchmark:
    candidate: str
    workload_id: str
    hardware_id: str
    successful_requests: int
    failed_requests: int
    ttft_p95_ms: float
    inter_token_p95_ms: float
    output_tokens_per_second: float
    recovery_seconds: float | None
    kv_reuse_ratio: float | None = None

    def __post_init__(self) -> None:
        if (
            not self.candidate.strip()
            or not self.workload_id.strip()
            or not self.hardware_id.strip()
        ):
            raise ValueError("Benchmark identity fields must not be blank.")
        if self.successful_requests < 1 or self.failed_requests < 0:
            raise ValueError("A benchmark needs successful requests and valid counts.")
        for value in (
            self.ttft_p95_ms,
            self.inter_token_p95_ms,
            self.output_tokens_per_second,
        ):
            if value < 0:
                raise ValueError("Benchmark measurements cannot be negative.")
        if self.recovery_seconds is not None and self.recovery_seconds < 0:
            raise ValueError("Recovery time cannot be negative.")
        if self.kv_reuse_ratio is not None and not 0 <= self.kv_reuse_ratio <= 1:
            raise ValueError("KV reuse ratio must be between zero and one.")


@dataclass(frozen=True, slots=True)
class AdoptionDecision:
    status: DecisionStatus
    reasons: tuple[str, ...]


def evaluate_candidate(
    baseline: ServingBenchmark,
    candidate: ServingBenchmark,
    *,
    minimum_throughput_gain: float = 0.10,
    maximum_ttft_regression: float = 0.05,
) -> AdoptionDecision:
    """Apply a conservative measured gate on an identical workload/hardware pair."""
    reasons: list[str] = []
    if (baseline.workload_id, baseline.hardware_id) != (
        candidate.workload_id,
        candidate.hardware_id,
    ):
        reasons.append("non_comparable_environment")
    if baseline.output_tokens_per_second <= 0:
        reasons.append("invalid_baseline_throughput")
    else:
        gain = (
            candidate.output_tokens_per_second / baseline.output_tokens_per_second - 1
        )
        if gain < minimum_throughput_gain:
            reasons.append("insufficient_throughput_gain")
    if baseline.ttft_p95_ms <= 0:
        reasons.append("invalid_baseline_ttft")
    elif candidate.ttft_p95_ms > baseline.ttft_p95_ms * (1 + maximum_ttft_regression):
        reasons.append("ttft_regression")
    if candidate.failed_requests > baseline.failed_requests:
        reasons.append("reliability_regression")
    if candidate.recovery_seconds is None:
        reasons.append("recovery_not_measured")
    return AdoptionDecision(
        DecisionStatus.HOLD if reasons else DecisionStatus.ADOPT,
        tuple(reasons) if reasons else ("measured_acceptance_thresholds_met",),
    )
