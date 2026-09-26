"""Validate the blocked-by-default model-allocation v3 governance record."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def wilson_lower(passed: int, total: int) -> float:
    z = 1.959963984540054
    proportion = passed / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return max(0.0, center - radius / denominator)


def minimum_passes(total: int, target: float) -> int:
    for passed in range(total + 1):
        if wilson_lower(passed, total) > target:
            return passed
    raise ValueError("No passing count can satisfy the requested lower bound")


def readiness_blockers(document: dict[str, Any]) -> tuple[str, ...]:
    readiness = document["readiness"]
    return tuple(
        field
        for field, value in readiness.items()
        if not isinstance(value, str) or not value.strip()
    )


def validate_governance(document: dict[str, Any]) -> tuple[str, ...]:
    sample = document["sample"]
    quality = document["quality_gate"]
    savings = document["savings_gate"]
    review = document["review"]
    cases = sample["matched_cases"]
    arms = sample["arms"]
    if type(cases) is not int or cases < 1:
        raise ValueError("matched_cases must be a positive integer")
    if (
        not isinstance(arms, list)
        or len(arms) != 2
        or any(not isinstance(arm, str) or not arm.strip() for arm in arms)
        or len(set(arms)) != 2
    ):
        raise ValueError("Exactly two unique matched arms are required")
    if sample["planned_calls"] != cases * len(arms):
        raise ValueError("planned_calls must equal matched cases times arms")
    if sum(sample["strata"].values()) != cases or any(
        type(count) is not int or count < 1 for count in sample["strata"].values()
    ):
        raise ValueError("Positive stratum counts must sum to matched_cases")
    if not all(
        sample[field] is expected
        for field, expected in (
            ("synthetic_or_public_only", True),
            ("held_out_from_candidates", True),
            ("case_reuse_from_v1_v2", False),
        )
    ):
        raise ValueError("Cases must be held-out synthetic/public inputs")
    target = quality["target_population_rate"]
    if type(target) is not float or not 0 < target < 1:
        raise ValueError("Population target must be a float between zero and one")
    if quality["minimum_allocation_passes"] != minimum_passes(cases, target):
        raise ValueError("Minimum pass count does not satisfy the Wilson gate")
    if (
        quality["confidence_level"] != 0.95
        or quality["critical_failures_allowed"] != 0
        or quality["all_pairs_must_be_graded"] is not True
        or quality["paired_interval_method"]
        != "Newcombe score interval for paired proportions"
        or type(quality["noninferiority_margin"]) is not float
        or not 0 <= quality["noninferiority_margin"] < 1
    ):
        raise ValueError("Quality gate is incomplete or unsupported")
    if (
        type(savings["minimum_cost_reduction"]) is not float
        or not 0 < savings["minimum_cost_reduction"] < 1
        or savings["require_complete_candidate_and_overhead_usage"] is not True
        or savings["require_applicable_billing_snapshot"] is not True
        or savings["quality_gate_must_pass_first"] is not True
    ):
        raise ValueError("Savings gate must fail closed")
    if (
        review["independent_required"] is not True
        or review["blind_to_arm_until_scores_are_frozen"] is not True
        or review["candidate_author_ids_recorded"] is not True
    ):
        raise ValueError("Independent blinded review is required")
    hard_stops = document["hard_stops"]
    if (
        not isinstance(hard_stops, list)
        or not hard_stops
        or any(not isinstance(item, str) or not item.strip() for item in hard_stops)
        or len(set(hard_stops)) != len(hard_stops)
    ):
        raise ValueError("Unique hard-stop failures are required")
    blockers = readiness_blockers(document)
    expected_status = "blocked" if blockers else "ready"
    if document["status"] != expected_status:
        raise ValueError("Governance status disagrees with readiness evidence")
    if not blockers:
        readiness = document["readiness"]
        for field in (
            "case_manifest_sha256",
            "paired_metric_implementation_sha256",
        ):
            value = readiness[field]
            if len(value) != 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise ValueError("Readiness hashes must be lowercase SHA-256 values")
        if readiness["curator_id"] == readiness["reviewer_id"]:
            raise ValueError("Case curator and independent reviewer must differ")
    return blockers


def load_governance(path: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise ValueError("Governance record must be an object")
    return document, validate_governance(document)
