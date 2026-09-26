"""Deterministic statistical gates for matched model-allocation evaluations."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import NormalDist
from typing import Any


@dataclass(frozen=True)
class PairedInterval:
    """Newcombe method 10 interval and its supporting 2x2 table."""

    both_pass: int
    allocation_only: int
    baseline_only: int
    both_fail: int
    total: int
    difference: float
    confidence_level: float
    lower: float
    upper: float
    method: str = "Newcombe method 10 score interval for paired proportions"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _count(value: int, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _wilson_bounds(successes: int, total: int, z: float) -> tuple[float, float]:
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return center - radius / denominator, center + radius / denominator


def newcombe_paired_interval(
    both_pass: int,
    allocation_only: int,
    baseline_only: int,
    both_fail: int,
    *,
    confidence_level: float = 0.95,
) -> PairedInterval:
    """Return Newcombe's method 10 interval for allocation minus baseline.

    The four arguments are the paired binary outcome cells ``e, f, g, h`` in
    Newcombe (1998), where ``f`` is allocation-only success and ``g`` is
    baseline-only success. Method 10 combines Wilson marginal score intervals
    and uses Newcombe's continuity-adjusted estimate of positive correlation.
    """

    e = _count(both_pass, "both_pass")
    f = _count(allocation_only, "allocation_only")
    g = _count(baseline_only, "baseline_only")
    h = _count(both_fail, "both_fail")
    if type(confidence_level) is not float or not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be a float between zero and one")
    total = e + f + g + h
    if total == 0:
        raise ValueError("at least one pair is required")

    allocation_rate = (e + f) / total
    baseline_rate = (e + g) / total
    difference = allocation_rate - baseline_rate
    z = NormalDist().inv_cdf(0.5 + confidence_level / 2)
    allocation_lower, allocation_upper = _wilson_bounds(e + f, total, z)
    baseline_lower, baseline_upper = _wilson_bounds(e + g, total, z)

    denominator = math.sqrt((e + f) * (g + h) * (e + g) * (f + h))
    raw_numerator = e * h - f * g
    if denominator == 0:
        correlation = 0.0
    elif raw_numerator > 0:
        correlation = max(raw_numerator - total / 2, 0.0) / denominator
    else:
        correlation = raw_numerator / denominator

    allocation_lower_gap = allocation_rate - allocation_lower
    allocation_upper_gap = allocation_upper - allocation_rate
    baseline_lower_gap = baseline_rate - baseline_lower
    baseline_upper_gap = baseline_upper - baseline_rate
    lower_distance = math.sqrt(
        allocation_lower_gap**2
        - 2 * correlation * allocation_lower_gap * baseline_upper_gap
        + baseline_upper_gap**2
    )
    upper_distance = math.sqrt(
        allocation_upper_gap**2
        - 2 * correlation * allocation_upper_gap * baseline_lower_gap
        + baseline_lower_gap**2
    )
    return PairedInterval(
        both_pass=e,
        allocation_only=f,
        baseline_only=g,
        both_fail=h,
        total=total,
        difference=difference,
        confidence_level=confidence_level,
        lower=max(-1.0, difference - lower_distance),
        upper=min(1.0, difference + upper_distance),
    )


def paired_noninferiority(
    interval: PairedInterval, *, margin: float
) -> dict[str, Any]:
    """Evaluate a strict lower-bound noninferiority gate."""

    if type(margin) is not float or not 0 <= margin < 1:
        raise ValueError(
            "margin must be a float from zero up to, but not including, one"
        )
    threshold = -margin
    return {
        "margin": margin,
        "required_lower_bound_above": threshold,
        "passed": interval.lower > threshold,
        "interval": interval.as_dict(),
    }
