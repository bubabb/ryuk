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


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
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
        and total == 26
        and invalid == 0
        and passed >= 23
        and critical == 0,
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
        "setup_and_reviewer_usage": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(PILOT.read_text())
    metadata = json.loads((args.directory / "run.json").read_text())
    if hashlib.sha256(PILOT.read_bytes()).hexdigest() != metadata["manifest_sha256"]:
        raise ValueError("Manifest changed after run began")
    review = json.loads(args.review.read_text())
    results = [grade_task(task, args.directory, review) for task in manifest["tasks"]]
    report = {"summary": summarize(results), "tasks": results}
    (args.directory / "grades.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
