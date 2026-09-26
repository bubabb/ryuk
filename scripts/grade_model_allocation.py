"""Grade reviewed pilot artifacts locally; no model or network calls."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # Support direct `python scripts/...py` invocation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_allocation_governance import load_governance  # noqa: E402
from scripts.model_allocation_manifest import load_manifest  # noqa: E402
from scripts.model_allocation_statistics import (  # noqa: E402
    newcombe_paired_interval,
    paired_noninferiority,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "evals/model_allocation/pilot.json"


def wilson(passed: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = passed / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return [
        max(0.0, center - radius / denominator),
        min(1.0, center + radius / denominator),
    ]


def safe_source(source: str) -> None:
    """Defense in depth, not a security sandbox; review is required separately."""
    tree = ast.parse(source)
    allowed_imports = {"math", "json", "hashlib", "sqlite3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in allowed_imports for alias in node.names):
                raise ValueError("Unapproved import")
        if isinstance(node, ast.ImportFrom) and node.module not in allowed_imports:
            raise ValueError("Unapproved import")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Dunder access")
        if isinstance(node, ast.Name) and node.id in {
            "exec",
            "eval",
            "compile",
            "open",
            "__import__",
            "globals",
            "locals",
            "getattr",
            "setattr",
            "input",
            "breakpoint",
        }:
            raise ValueError("Unapproved builtin")


def grade_task(
    task: dict[str, Any], directory: Path, review: dict[str, Any]
) -> dict[str, Any]:
    folder = directory / task["id"]
    result: dict[str, Any] = {
        "id": task["id"],
        "model": task["model"],
        "category": task["category"],
        "critical_task": task["critical"],
        "grade": "unrun",
    }
    if "case_id" in task:
        result["case_id"] = task["case_id"]
        result["arm"] = task["arm"]
    if not (folder / "measurement.json").exists():
        return result
    measurement = json.loads((folder / "measurement.json").read_text())
    result["usage"] = measurement.get("usage")
    result["seconds"] = measurement.get("seconds")
    if measurement["status"] != "completed":
        result["reason"] = measurement["status"]
        return result
    if task["id"] in review.get("invalid_tasks", {}):
        return {
            **result,
            "grade": "invalid_task",
            "reason": review["invalid_tasks"][task["id"]],
        }
    if measurement.get("tool_items"):
        return {**result, "grade": "fail", "reason": "tool_use_violation"}
    try:
        payload = json.loads((folder / "response.json").read_text())
        source = payload["content"]
        if not isinstance(source, str) or len(source) > 50000:
            raise ValueError("Invalid content")
    except (OSError, ValueError, KeyError):
        return {**result, "grade": "fail", "reason": "invalid_response"}
    if task["expected"] is not None:
        try:
            actual = json.loads(source)
            # JSON canonical comparison distinguishes booleans from integers.
            passed = json.dumps(actual, sort_keys=True) == json.dumps(
                task["expected"], sort_keys=True
            )
        except ValueError:
            passed = False
        return {**result, "grade": "pass" if passed else "fail", "reason": "exact_json"}
    inspected = review.get(task["id"])
    if not inspected:
        return {**result, "grade": "pending_review"}
    response_hash = hashlib.sha256((folder / "response.json").read_bytes()).hexdigest()
    if inspected.get("response_sha256") != response_hash:
        return {**result, "grade": "pending_review", "reason": "review_hash_mismatch"}
    if not inspected["pass"]:
        return {**result, "grade": "fail", "reason": inspected["notes"]}
    if task["model"] == "gpt-6-astra":
        return {**result, "grade": "pass", "reason": inspected["notes"]}
    try:
        safe_source(source)
        with tempfile.TemporaryDirectory(prefix="ryuk-pilot-grade-") as workspace:
            script = Path(workspace) / "candidate.py"
            script.write_text(source + "\n\n" + "\n".join(task["checks"]) + "\n")
            completed = subprocess.run(
                [sys.executable, "-I", "-S", str(script)],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            passed = completed.returncode == 0
            if not passed:
                # Artifacts are synthetic. Preserve assertion diagnostics for review.
                (folder / "test_failure.txt").write_text(completed.stderr)
    except (ValueError, SyntaxError, subprocess.TimeoutExpired) as failure:
        return {**result, "grade": "fail", "reason": type(failure).__name__}
    return {
        **result,
        "grade": "pass" if passed else "fail",
        "reason": "hidden_assertions_and_review",
    }


def summarize(
    results: list[dict[str, Any]],
    threshold: dict[str, int] | None = None,
    comparison: dict[str, Any] | None = None,
    overhead: dict[str, Any] | None = None,
    noninferiority_margin: float | None = None,
) -> dict[str, Any]:
    threshold = threshold or {
        "planned_tasks": 26,
        "minimum_first_pass": 23,
        "critical_failures_allowed": 0,
    }
    passed = sum(row["grade"] == "pass" for row in results)
    failed = sum(row["grade"] == "fail" for row in results)
    critical = sum(row["grade"] == "fail" and row["critical_task"] for row in results)
    total = len(results)
    invalid = sum(row["grade"] == "invalid_task" for row in results)
    unrun = sum(row["grade"] not in ("pass", "fail", "invalid_task") for row in results)
    complete = unrun == 0
    strata = {}
    for model in sorted({row["model"] for row in results}):
        subset = [row for row in results if row["model"] == model]
        p = sum(row["grade"] == "pass" for row in subset)
        f = sum(row["grade"] == "fail" for row in subset)
        strata[model] = {
            "planned": len(subset),
            "passed": p,
            "failed": f,
            "ungraded": sum(row["grade"] not in ("pass", "fail") for row in subset),
            "observed_rate": p / (p + f) if p + f else None,
            "wilson_95_interval": wilson(p, p + f),
        }
    interval = wilson(passed, passed + failed)
    usage = {}
    for field in (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    ):
        values = [
            row.get("usage", {}).get(field) if row.get("usage") else None
            for row in results
        ]
        usage[field] = (
            sum(x for x in values if isinstance(x, int))
            if all(isinstance(x, int) for x in values)
            else None
        )
    by_model_usage: dict[str, Any] = {}
    for model in sorted({row["model"] for row in results}):
        subset = [row for row in results if row["model"] == model]
        available = [
            row["usage"] for row in subset if isinstance(row.get("usage"), dict)
        ]
        by_model_usage[model] = {
            "calls_planned": len(subset),
            "calls_with_usage": len(available),
            "calls_usage_unknown": len(subset) - len(available),
            **{
                field: sum(item[field] for item in available)
                if available and all(field in item for item in available)
                else None
                for field in (
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                )
            },
        }
    summary = {
        "planned": total,
        "passed": passed,
        "failed": failed,
        "invalid_tasks": invalid,
        "unrun": unrun,
        "ungraded": invalid + unrun,
        "complete": complete,
        "critical_failures": critical,
        "valid_scored_tasks": passed + failed,
        "observed_rate": passed / (passed + failed) if passed + failed else None,
        "pilot_gate_passed": complete
        and total == threshold["planned_tasks"]
        and invalid == 0
        and passed >= threshold["minimum_first_pass"]
        and critical <= threshold["critical_failures_allowed"],
        "wilson_95_interval": interval,
        "lower_bound_exceeds_87_percent": complete
        and invalid == 0
        and interval is not None
        and interval[0] > 0.87,
        "population_claim_valid": False,
        "limitation": (
            "Small purposive synthetic sample; "
            "no population reliability or savings claim."
        ),
        "by_model": strata,
        "candidate_usage": usage,
        "recorded_candidate_usage_by_model": by_model_usage,
        "setup_and_reviewer_usage": overhead,
    }
    usage_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    total_usage: dict[str, int | None]
    if overhead is None:
        total_usage = {field: None for field in usage_fields}
    else:
        total_usage = {}
        for field in usage_fields:
            values = [usage[field], *(item[field] for item in overhead.values())]
            total_usage[field] = (
                sum(item for item in values if type(item) is int)
                if all(type(item) is int for item in values)
                else None
            )
    summary["total_recorded_usage"] = total_usage
    summary["usage_complete"] = all(
        type(total_usage[field]) is int for field in usage_fields
    )
    if comparison is not None:
        arms = comparison["arms"]
        by_arm = {}
        for arm in arms:
            subset = [row for row in results if row["arm"] == arm]
            by_arm[arm] = {
                "planned": len(subset),
                "passed": sum(row["grade"] == "pass" for row in subset),
                "failed": sum(row["grade"] == "fail" for row in subset),
                "ungraded": sum(row["grade"] not in ("pass", "fail") for row in subset),
            }
        summary["by_arm"] = by_arm
        paired: dict[str, Any] = {
            "complete_pairs": 0,
            "incomplete_pairs": 0,
            "outcomes": {},
        }
        cases = sorted({row["case_id"] for row in results})
        for case_id in cases:
            rows = {row["arm"]: row for row in results if row["case_id"] == case_id}
            if set(rows) != set(arms) or any(
                rows[arm]["grade"] not in ("pass", "fail") for arm in arms
            ):
                paired["incomplete_pairs"] += 1
                continue
            paired["complete_pairs"] += 1
            key = "/".join(f"{arm}:{rows[arm]['grade']}" for arm in arms)
            paired["outcomes"][key] = paired["outcomes"].get(key, 0) + 1
        summary["matched_comparison"] = paired
        if paired["incomplete_pairs"] == 0 and noninferiority_margin is not None:
            allocation, baseline = arms
            outcome = paired["outcomes"]
            paired_interval = newcombe_paired_interval(
                outcome.get(f"{allocation}:pass/{baseline}:pass", 0),
                outcome.get(f"{allocation}:pass/{baseline}:fail", 0),
                outcome.get(f"{allocation}:fail/{baseline}:pass", 0),
                outcome.get(f"{allocation}:fail/{baseline}:fail", 0),
            )
            paired["noninferiority"] = paired_noninferiority(
                paired_interval, margin=noninferiority_margin
            )
    return summary


def validate_review_declaration(
    manifest: dict[str, Any], review: dict[str, Any]
) -> None:
    policy = manifest.get("review") or {}
    if not isinstance(policy, dict):
        raise ValueError("Review policy must be an object")
    if not policy.get("require_independent"):
        return
    metadata = review.get("_meta")
    if not isinstance(metadata, dict):
        raise ValueError("Independent review metadata is required")
    reviewer = metadata.get("reviewer_id")
    authors = metadata.get("candidate_author_ids")
    if (
        metadata.get("independent") is not True
        or not isinstance(reviewer, str)
        or not reviewer.strip()
        or not isinstance(authors, list)
        or not authors
        or any(not isinstance(author, str) or not author.strip() for author in authors)
        or reviewer in authors
    ):
        raise ValueError("Independent review declaration is invalid")


def load_overhead(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text())
    fields = {
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    }
    if not isinstance(value, dict) or not value:
        raise ValueError("Overhead ledger must contain named categories")
    for category, usage in value.items():
        if (
            not isinstance(category, str)
            or not category.strip()
            or not isinstance(usage, dict)
        ):
            raise ValueError("Invalid overhead category")
        if set(usage) != fields or any(
            item is not None and (type(item) is not int or item < 0)
            for item in usage.values()
        ):
            raise ValueError(
                "Overhead usage fields must be nonnegative integers or null"
            )
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=PILOT)
    parser.add_argument("--overhead", type=Path)
    parser.add_argument("--governance", type=Path)
    args = parser.parse_args()
    manifest, manifest_digest = load_manifest(args.manifest.resolve())
    noninferiority_margin = None
    if manifest.get("version") == 3:
        if args.governance is None:
            raise ValueError("Version 3 grading requires a governance record")
        governance, blockers = load_governance(args.governance.resolve())
        if blockers:
            raise ValueError(
                "Version 3 grading requires complete governance; missing: "
                + ", ".join(blockers)
            )
        if governance["readiness"]["case_manifest_sha256"] != manifest_digest:
            raise ValueError("Governance is not bound to this manifest")
        noninferiority_margin = governance["quality_gate"][
            "noninferiority_margin"
        ]
    metadata = json.loads((args.directory / "run.json").read_text())
    if manifest_digest != metadata["manifest_sha256"]:
        raise ValueError("Manifest changed after run began")
    review = json.loads(args.review.read_text())
    validate_review_declaration(manifest, review)
    overhead = load_overhead(args.overhead)
    results = [grade_task(task, args.directory, review) for task in manifest["tasks"]]
    report = {
        "summary": summarize(
            results,
            manifest["threshold"],
            manifest.get("comparison"),
            overhead,
            noninferiority_margin,
        ),
        "tasks": results,
    }
    (args.directory / "grades.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
