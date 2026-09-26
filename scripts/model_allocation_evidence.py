"""Validate blinded review and all-in savings evidence for v3 evaluations."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
OVERHEAD_CATEGORIES = {"setup", "grading", "review"}
ARMS = ("allocation", "all_astra_baseline")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")
BLIND_ID_RE = re.compile(r"^B(?:00[1-9]|0[1-9][0-9]|1[0-9]{2}|200)$")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def response_set_sha256(manifest: dict[str, Any], directory: Path) -> str:
    """Hash the ordered task-to-response digest map for the complete run."""

    bindings = []
    for task in sorted(manifest["tasks"], key=lambda item: item["id"]):
        path = directory / task["id"] / "response.json"
        if not path.is_file():
            raise ValueError("Every task must have a response artifact")
        bindings.append({"task_id": task["id"], "response_sha256": file_sha256(path)})
    return hashlib.sha256(
        json.dumps(bindings, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_candidate_measurements(
    manifest: dict[str, Any], directory: Path
) -> None:
    """Require one complete, usage-bearing measurement for every planned call."""

    for task in manifest["tasks"]:
        path = directory / task["id"] / "measurement.json"
        if not path.is_file():
            raise ValueError("Every task must have a measurement artifact")
        measurement = json.loads(path.read_text())
        if not isinstance(measurement, dict):
            raise ValueError("Every measurement must be an object")
        if (
            measurement.get("id") != task["id"]
            or measurement.get("status") != "completed"
            or measurement.get("model_requested") != task["model"]
            or measurement.get("effort") != task["effort"]
        ):
            raise ValueError("Candidate measurement differs from the manifest")
        _usage(measurement.get("usage"), "candidate usage")


def _exact(value: dict[str, Any], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields must be exactly {sorted(fields)}")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _sha(value: Any, name: str) -> str:
    text = _text(value, name)
    if SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 value")
    return text


def _timestamp(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as failure:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from failure
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def _usage(value: Any, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(TOKEN_FIELDS):
        raise ValueError(f"{name} must contain the four token counters")
    if any(type(value[field]) is not int or value[field] < 0 for field in TOKEN_FIELDS):
        raise ValueError(f"{name} token counters must be nonnegative integers")
    if value["cached_input_tokens"] > value["input_tokens"]:
        raise ValueError(f"{name} cached input cannot exceed input tokens")
    return value


def validate_blinded_review_ledger(
    document: dict[str, Any],
    manifest: dict[str, Any],
    *,
    manifest_sha256: str,
    run_sha256: str,
    response_directory: Path | None = None,
) -> None:
    """Validate finalized aliases, bindings, independence, and blind sequencing."""

    _exact(
        document,
        {
            "version",
            "manifest_sha256",
            "run_sha256",
            "response_set_sha256",
            "reviewer_id",
            "candidate_author_ids",
            "independent",
            "blinding",
            "reviews",
        },
        "review ledger",
    )
    if document["version"] != 1:
        raise ValueError("Review ledger version must be 1")
    if _sha(document["manifest_sha256"], "manifest_sha256") != manifest_sha256:
        raise ValueError("Review ledger is not bound to this manifest")
    if _sha(document["run_sha256"], "run_sha256") != run_sha256:
        raise ValueError("Review ledger is not bound to this run")
    recorded_response_set = _sha(
        document["response_set_sha256"], "response_set_sha256"
    )
    if response_directory is not None and recorded_response_set != response_set_sha256(
        manifest, response_directory
    ):
        raise ValueError("Review ledger response set hash mismatch")
    reviewer = _text(document["reviewer_id"], "reviewer_id")
    authors = document["candidate_author_ids"]
    if (
        not isinstance(authors, list)
        or not authors
        or any(not isinstance(author, str) or not author.strip() for author in authors)
        or len(set(authors)) != len(authors)
    ):
        raise ValueError("candidate_author_ids must be unique nonblank strings")
    policy = manifest.get("review")
    if not isinstance(policy, dict) or policy.get("require_independent") is not True:
        raise ValueError("Manifest must require independent review")
    if authors != policy.get("candidate_author_ids"):
        raise ValueError("Review candidate authors differ from the manifest")
    if document["independent"] is not True or reviewer in authors:
        raise ValueError("Reviewer must be independent from candidate authors")

    blinding = document["blinding"]
    if not isinstance(blinding, dict):
        raise ValueError("blinding must be an object")
    _exact(
        blinding,
        {
            "alias_map_sha256",
            "arm_labels_hidden_until_scores_frozen",
            "scores_frozen_at",
            "unblinded_at",
        },
        "blinding",
    )
    if blinding["arm_labels_hidden_until_scores_frozen"] is not True:
        raise ValueError("Arm labels must stay hidden until scores are frozen")
    frozen = _timestamp(blinding["scores_frozen_at"], "scores_frozen_at")
    unblinded = _timestamp(blinding["unblinded_at"], "unblinded_at")
    if unblinded <= frozen:
        raise ValueError("Unblinding must occur after frozen scores")

    required = {task["id"] for task in manifest["tasks"] if task["expected"] is None}
    reviews = document["reviews"]
    if not isinstance(reviews, list) or len(reviews) != len(required):
        raise ValueError("Review ledger must cover every review-required task")
    aliases: set[str] = set()
    task_ids: set[str] = set()
    alias_map: list[dict[str, str]] = []
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("Every review must be an object")
        _exact(
            review,
            {"blind_id", "task_id", "response_sha256", "verdict", "notes"},
            "review",
        )
        blind_id = _text(review["blind_id"], "blind_id")
        task_id = _text(review["task_id"], "task_id")
        if BLIND_ID_RE.fullmatch(blind_id) is None or blind_id in aliases:
            raise ValueError("Blind IDs must be unique B001 through B200")
        if task_id in task_ids:
            raise ValueError("Review task IDs must be unique")
        aliases.add(blind_id)
        task_ids.add(task_id)
        _sha(review["response_sha256"], "response_sha256")
        if response_directory is not None:
            response_path = response_directory / task_id / "response.json"
            if not response_path.is_file() or file_sha256(response_path) != review[
                "response_sha256"
            ]:
                raise ValueError("Review response hash mismatch")
        if review["verdict"] not in {"pass", "fail", "invalid_task"}:
            raise ValueError("Review verdict is unsupported")
        _text(review["notes"], "review notes")
        alias_map.append({"blind_id": blind_id, "task_id": task_id})
    if task_ids != required:
        raise ValueError("Review task IDs do not match review-required tasks")
    alias_digest = hashlib.sha256(
        json.dumps(alias_map, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if _sha(blinding["alias_map_sha256"], "alias_map_sha256") != alias_digest:
        raise ValueError("Blinded alias map hash mismatch")


def compile_review_for_grader(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated finalized ledger to the legacy grader input shape."""

    review: dict[str, Any] = {
        "_meta": {
            "reviewer_id": document["reviewer_id"],
            "candidate_author_ids": document["candidate_author_ids"],
            "independent": document["independent"],
        },
        "invalid_tasks": {},
    }
    for item in document["reviews"]:
        if item["verdict"] == "invalid_task":
            review["invalid_tasks"][item["task_id"]] = item["notes"]
        else:
            review[item["task_id"]] = {
                "pass": item["verdict"] == "pass",
                "notes": item["notes"],
                "response_sha256": item["response_sha256"],
            }
    return review


def _rate(value: Any, name: str) -> Decimal:
    if not isinstance(value, str) or DECIMAL_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a nonnegative decimal string")
    try:
        rate = Decimal(value)
    except InvalidOperation as failure:
        raise ValueError(f"{name} must be a nonnegative decimal string") from failure
    if not rate.is_finite() or rate < 0:
        raise ValueError(f"{name} must be a nonnegative decimal string")
    return rate


def validate_savings_evidence(
    document: dict[str, Any],
    *,
    manifest_sha256: str,
    run_sha256: str,
    review_ledger_sha256: str,
    billing_snapshot_id: str,
) -> None:
    """Validate hash bindings, applicable rates, and complete arm overhead."""

    _exact(
        document,
        {
            "version",
            "manifest_sha256",
            "run_sha256",
            "review_ledger_sha256",
            "billing_snapshot",
            "overhead",
        },
        "savings evidence",
    )
    if document["version"] != 1:
        raise ValueError("Savings evidence version must be 1")
    for field, expected in (
        ("manifest_sha256", manifest_sha256),
        ("run_sha256", run_sha256),
        ("review_ledger_sha256", review_ledger_sha256),
    ):
        if _sha(document[field], field) != expected:
            raise ValueError(f"Savings evidence {field} binding mismatch")
    billing = document["billing_snapshot"]
    if not isinstance(billing, dict):
        raise ValueError("billing_snapshot must be an object")
    _exact(
        billing,
        {
            "id",
            "captured_at",
            "currency",
            "source_reference",
            "applicable_to_run",
            "reasoning_output_billed_separately",
            "model_rates",
        },
        "billing_snapshot",
    )
    if _text(billing["id"], "billing snapshot id") != billing_snapshot_id:
        raise ValueError("Billing snapshot does not match governance")
    _timestamp(billing["captured_at"], "billing captured_at")
    if billing["currency"] != "USD" or billing["applicable_to_run"] is not True:
        raise ValueError("Billing snapshot must be applicable USD evidence")
    if billing["reasoning_output_billed_separately"] is not False:
        raise ValueError("Reasoning tokens must be included in output token billing")
    _text(billing["source_reference"], "billing source_reference")
    rates = billing["model_rates"]
    if not isinstance(rates, dict) or not rates:
        raise ValueError("Billing snapshot needs model rates")
    for model, rate in rates.items():
        _text(model, "billing model")
        if not isinstance(rate, dict):
            raise ValueError("Every model rate must be an object")
        _exact(
            rate,
            {
                "input_usd_per_million_tokens",
                "cached_input_usd_per_million_tokens",
                "output_usd_per_million_tokens",
            },
            "model rate",
        )
        for field, value in rate.items():
            _rate(value, field)

    overhead = document["overhead"]
    if not isinstance(overhead, list) or len(overhead) != 6:
        raise ValueError("Overhead must contain setup, grading, and review per arm")
    seen: set[tuple[str, str]] = set()
    for item in overhead:
        if not isinstance(item, dict):
            raise ValueError("Every overhead item must be an object")
        _exact(item, {"arm", "category", "model", "usage"}, "overhead item")
        arm, category, model = item["arm"], item["category"], item["model"]
        if arm not in ARMS or category not in OVERHEAD_CATEGORIES:
            raise ValueError("Overhead arm or category is unsupported")
        if (arm, category) in seen:
            raise ValueError("Overhead arm/category entries must be unique")
        seen.add((arm, category))
        if model not in rates:
            raise ValueError("Every overhead model needs a billing rate")
        _usage(item["usage"], "overhead usage")
    if seen != {(arm, category) for arm in ARMS for category in OVERHEAD_CATEGORIES}:
        raise ValueError("Overhead coverage is incomplete")


def _cost(usage: dict[str, int], rate: dict[str, str]) -> Decimal:
    uncached = usage["input_tokens"] - usage["cached_input_tokens"]
    numerator = (
        Decimal(uncached) * Decimal(rate["input_usd_per_million_tokens"])
        + Decimal(usage["cached_input_tokens"])
        * Decimal(rate["cached_input_usd_per_million_tokens"])
        + Decimal(usage["output_tokens"])
        * Decimal(rate["output_usd_per_million_tokens"])
    )
    return numerator / Decimal(1_000_000)


def evaluate_savings(
    results: list[dict[str, Any]],
    document: dict[str, Any],
    *,
    quality_gate_passed: bool,
    minimum_cost_reduction: float,
) -> dict[str, Any]:
    """Recompute arm costs; incomplete evidence raises instead of becoming zero."""

    rates = document["billing_snapshot"]["model_rates"]
    costs = {arm: Decimal(0) for arm in ARMS}
    for result in results:
        arm = result.get("arm")
        model = result.get("model")
        if arm not in ARMS or model not in rates:
            raise ValueError("Every candidate call needs an arm and billing rate")
        usage = _usage(result.get("usage"), "candidate usage")
        costs[arm] += _cost(usage, rates[model])
    for item in document["overhead"]:
        costs[item["arm"]] += _cost(item["usage"], rates[item["model"]])
    baseline = costs["all_astra_baseline"]
    if baseline <= 0:
        raise ValueError("Baseline all-in cost must be positive")
    reduction = (baseline - costs["allocation"]) / baseline
    threshold = Decimal(str(minimum_cost_reduction))
    return {
        "quality_gate_passed_first": quality_gate_passed,
        "minimum_cost_reduction": str(threshold),
        "allocation_cost_usd": str(costs["allocation"]),
        "baseline_cost_usd": str(baseline),
        "cost_reduction": str(reduction),
        "passed": quality_gate_passed and reduction >= threshold,
    }
