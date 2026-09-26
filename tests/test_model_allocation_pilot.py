import hashlib
import json

import pytest

from scripts.evaluate_model_allocation import (
    PILOT,
    prepare_infrastructure_retry,
    prompt_for,
)
from scripts.grade_model_allocation import (
    grade_task,
    load_overhead,
    summarize,
    validate_review_declaration,
    wilson,
)
from scripts.model_allocation_manifest import load_manifest, validate_manifest


def test_manifest_is_complete_and_candidate_prompt_hides_grading():
    manifest, digest = load_manifest(PILOT)
    assert digest == hashlib.sha256(PILOT.read_bytes()).hexdigest()
    tasks = manifest["tasks"]
    assert len({task["id"] for task in tasks}) == len(tasks) == 26
    assert sum(task["model"] == "gpt-6-luna" for task in tasks) == 8
    assert sum(task["model"] == "gpt-6-sol" for task in tasks) == 12
    assert sum(task["model"] == "gpt-6-astra" for task in tasks) == 6
    for task in tasks:
        prompt = prompt_for(task)
        hidden = {**task, "expected": "GRADING_SECRET", "checks": ["HIDDEN_CHECK"]}
        assert prompt_for(hidden) == prompt
        assert "assert " not in prompt
        assert task["prompt"] in prompt


def test_v2_manifest_resolves_typed_evidence_and_migration_cardinality():
    manifest, digest = load_manifest(PILOT.with_name("pilot-v2.json"))
    tasks = {task["id"]: task for task in manifest["tasks"]}
    assert manifest["version"] == 2
    assert len(tasks) == 26
    assert len(digest) == 64
    assert tasks["P02"]["expected"]["offline_passed_count"] == 359
    assert type(tasks["P02"]["expected"]["offline_passed_count"]) is int
    assert "(integer)" in tasks["P02"]["prompt"]
    p20_checks = "\n".join(tasks["P20"]["checks"])
    assert "rows in [[], [(1,), (1,)], [(1,), (2,)]]" in p20_checks
    assert manifest["resume_policy"] == {
        "retry_statuses": ["infrastructure_error", "infrastructure_timeout"],
        "maximum_infrastructure_attempts_per_task": 2,
        "quality_failures_retryable": False,
    }


def test_manifest_digest_changes_when_base_or_overlay_changes(tmp_path):
    base = tmp_path / "base.json"
    overlay = tmp_path / "v2.json"
    base.write_text(
        json.dumps(
            {
                "version": 1,
                "threshold": {},
                "tasks": [{"id": "P01", "prompt": "a", "checks": []}],
            }
        )
    )
    overlay.write_text(json.dumps({"version": 2, "base_manifest": "base.json"}))
    _, first = load_manifest(overlay)
    base.write_text(base.read_text().replace('"a"', '"b"'))
    _, second = load_manifest(overlay)
    assert first != second


def test_resume_archives_only_one_declared_infrastructure_failure(tmp_path):
    folder = tmp_path / "P21"
    folder.mkdir()
    measurement = folder / "measurement.json"
    policy = {
        "retry_statuses": ["infrastructure_error", "infrastructure_timeout"],
        "maximum_infrastructure_attempts_per_task": 2,
    }
    measurement.write_text(json.dumps({"status": "infrastructure_error"}))
    prepare_infrastructure_retry(measurement, policy)
    assert json.loads((folder / "infrastructure_attempts/001.json").read_text()) == {
        "status": "infrastructure_error"
    }
    with pytest.raises(ValueError, match="retry limit"):
        prepare_infrastructure_retry(measurement, policy)

    completed = tmp_path / "P22"
    completed.mkdir()
    completed_measurement = completed / "measurement.json"
    completed_measurement.write_text(json.dumps({"status": "completed"}))
    with pytest.raises(ValueError, match="only for declared infrastructure"):
        prepare_infrastructure_retry(completed_measurement, policy)


def rows(passed=26):
    return [
        {
            "id": f"P{i}",
            "model": "test",
            "critical_task": False,
            "grade": "pass" if i < passed else "fail",
            "usage": None,
        }
        for i in range(26)
    ]


def test_threshold_and_critical_failure_and_missing_results():
    assert summarize(rows(23))["pilot_gate_passed"]
    assert not summarize(rows(22))["pilot_gate_passed"]
    critical = rows(25)
    critical[-1]["critical_task"] = True
    assert not summarize(critical)["pilot_gate_passed"]
    incomplete = rows()
    incomplete[-1]["grade"] = "unrun"
    summary = summarize(incomplete)
    assert not summary["complete"] and not summary["pilot_gate_passed"]
    assert summary["observed_rate"] == 1.0
    assert summary["valid_scored_tasks"] == 25
    assert summary["candidate_usage"]["input_tokens"] is None


def test_invalid_and_unrun_tasks_and_critical_failure_block_pilot_gate():
    results = rows(23)
    results[0]["grade"] = "fail"
    results[0]["critical_task"] = True
    results[1]["grade"] = "invalid_task"
    results[2]["grade"] = "unrun"
    summary = summarize(results)
    assert summary["passed"] == 20
    assert summary["invalid_tasks"] == 1
    assert summary["unrun"] == 1
    assert summary["critical_failures"] == 1
    assert not summary["pilot_gate_passed"]


def test_usage_aggregates_report_unknown_infrastructure_consumption():
    results = rows()
    for index, row in enumerate(results):
        row["model"] = "gpt-6-astra" if index == 25 else "gpt-6-luna"
        row["usage"] = {
            "input_tokens": 4,
            "cached_input_tokens": 1,
            "output_tokens": 2,
            "reasoning_output_tokens": 0,
        }
    results[25]["usage"] = None
    totals = summarize(results)["recorded_candidate_usage_by_model"]
    assert totals["gpt-6-luna"]["input_tokens"] == 100
    assert totals["gpt-6-luna"]["calls_usage_unknown"] == 0
    assert totals["gpt-6-astra"]["input_tokens"] is None
    assert totals["gpt-6-astra"]["calls_usage_unknown"] == 1


def test_wilson_does_not_turn_small_sample_into_87_percent_assurance():
    interval = wilson(23, 26)
    assert interval is not None and interval[0] < 0.87 < interval[1]
    perfect = wilson(26, 26)
    assert perfect is not None and perfect[0] == pytest.approx(0.8712710781)
    assert not summarize(rows())["population_claim_valid"]
    assert wilson(0, 0) is None


def test_review_is_required_and_bound_to_response_hash(tmp_path):
    task = {
        "id": "P21",
        "model": "gpt-6-astra",
        "category": "review",
        "critical": True,
        "expected": None,
    }
    folder = tmp_path / "P21"
    folder.mkdir()
    (folder / "measurement.json").write_text(json.dumps({"status": "completed"}))
    response = folder / "response.json"
    response.write_text(json.dumps({"content": "synthetic answer"}))
    assert grade_task(task, tmp_path, {})["grade"] == "pending_review"
    review = {
        "P21": {
            "pass": True,
            "notes": "reviewed",
            "response_sha256": hashlib.sha256(response.read_bytes()).hexdigest(),
        }
    }
    assert grade_task(task, tmp_path, review)["grade"] == "pass"
    response.write_text(json.dumps({"content": "changed"}))
    assert grade_task(task, tmp_path, review)["grade"] == "pending_review"


def test_exact_grading_rejects_boolean_integer_confusion(tmp_path):
    task = {
        "id": "P01",
        "model": "gpt-6-luna",
        "category": "extract",
        "critical": False,
        "expected": {"count": 1},
    }
    folder = tmp_path / "P01"
    folder.mkdir()
    (folder / "measurement.json").write_text(json.dumps({"status": "completed"}))
    (folder / "response.json").write_text(json.dumps({"content": '{"count":true}'}))
    assert grade_task(task, tmp_path, {})["grade"] == "fail"


def test_grader_rejects_dangerous_source():
    from scripts.grade_model_allocation import safe_source

    for source in ("import os", "open('file')", "().__class__", "eval('1')"):
        with pytest.raises(ValueError):
            safe_source(source)


def matched_manifest():
    shared = {
        "category": "matched",
        "prompt": "Return synthetic output",
        "expected": {"ok": True},
        "checks": None,
        "critical": False,
    }
    return {
        "comparison": {
            "arms": ["allocation", "baseline"],
            "baseline_arm": "baseline",
            "require_complete_pairs": True,
        },
        "tasks": [
            {
                **shared,
                "id": f"{case}-{arm}",
                "case_id": case,
                "arm": arm,
                "model": "test",
            }
            for case in ("C01", "C02")
            for arm in ("allocation", "baseline")
        ],
    }


def test_matched_manifest_requires_identical_complete_arms():
    manifest = matched_manifest()
    validate_manifest(manifest)
    manifest["tasks"].pop()
    with pytest.raises(ValueError, match="exactly once"):
        validate_manifest(manifest)
    manifest = matched_manifest()
    manifest["tasks"][1]["prompt"] = "different"
    with pytest.raises(ValueError, match="differs across arms"):
        validate_manifest(manifest)
    manifest = matched_manifest()
    manifest["comparison"]["arms"] = ["allocation", {}]
    with pytest.raises(ValueError, match="unique nonblank"):
        validate_manifest(manifest)
    manifest = matched_manifest()
    manifest["comparison"]["require_complete_pairs"] = False
    with pytest.raises(ValueError, match="complete pairs"):
        validate_manifest(manifest)


def test_matched_summary_reports_pairs_and_incomplete_results():
    results = [
        {
            "id": f"{case}-{arm}",
            "case_id": case,
            "arm": arm,
            "model": "test",
            "critical_task": False,
            "grade": grade,
            "usage": None,
        }
        for case, arm, grade in (
            ("C01", "allocation", "pass"),
            ("C01", "baseline", "fail"),
            ("C02", "allocation", "pass"),
            ("C02", "baseline", "unrun"),
        )
    ]
    comparison = matched_manifest()["comparison"]
    summary = summarize(
        results,
        {
            "planned_tasks": 4,
            "minimum_first_pass": 4,
            "critical_failures_allowed": 0,
        },
        comparison,
    )
    assert summary["by_arm"]["allocation"] == {
        "planned": 2,
        "passed": 2,
        "failed": 0,
        "ungraded": 0,
    }
    assert summary["matched_comparison"] == {
        "complete_pairs": 1,
        "incomplete_pairs": 1,
        "outcomes": {"allocation:pass/baseline:fail": 1},
    }


def test_complete_matched_summary_applies_paired_noninferiority_gate():
    results = []
    outcomes = [("pass", "pass")] * 90 + [("pass", "fail")] * 5 + [
        ("fail", "pass")
    ] * 3 + [("fail", "fail")] * 2
    for index, (allocation_grade, baseline_grade) in enumerate(outcomes):
        for arm, grade in (
            ("allocation", allocation_grade),
            ("all_astra_baseline", baseline_grade),
        ):
            results.append(
                {
                    "id": f"C{index:03}-{arm}",
                    "case_id": f"C{index:03}",
                    "arm": arm,
                    "model": "test",
                    "critical_task": False,
                    "grade": grade,
                    "usage": None,
                }
            )
    summary = summarize(
        results,
        comparison={"arms": ["allocation", "all_astra_baseline"]},
        noninferiority_margin=0.03,
    )
    gate = summary["matched_comparison"]["noninferiority"]
    assert gate["interval"]["difference"] == pytest.approx(0.02)
    assert gate["passed"] is False


def test_independent_review_declaration_is_enforced():
    manifest = {"review": {"require_independent": True}}
    valid = {
        "_meta": {
            "reviewer_id": "reviewer-a",
            "candidate_author_ids": ["candidate-a", "candidate-b"],
            "independent": True,
        }
    }
    validate_review_declaration(manifest, valid)
    for invalid in (
        {},
        {
            "_meta": {
                "reviewer_id": "same",
                "candidate_author_ids": ["same"],
                "independent": True,
            }
        },
        {
            "_meta": {
                "reviewer_id": "reviewer",
                "candidate_author_ids": ["candidate"],
                "independent": False,
            }
        },
    ):
        with pytest.raises(ValueError, match="Independent review"):
            validate_review_declaration(manifest, invalid)


def test_overhead_ledger_preserves_unknown_usage(tmp_path):
    path = tmp_path / "overhead.json"
    path.write_text(
        json.dumps(
            {
                "review": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 3,
                    "reasoning_output_tokens": None,
                }
            }
        )
    )
    loaded = load_overhead(path)
    assert loaded is not None
    assert loaded["review"]["reasoning_output_tokens"] is None
    results = rows()
    for row in results:
        row["usage"] = {
            "input_tokens": 1,
            "cached_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
        }
    summary = summarize(results, overhead=loaded)
    assert summary["total_recorded_usage"] == {
        "input_tokens": 36,
        "cached_input_tokens": 2,
        "output_tokens": 29,
        "reasoning_output_tokens": None,
    }
    assert not summary["usage_complete"]
    path.write_text(json.dumps({"review": {"input_tokens": -1}}))
    with pytest.raises(ValueError, match="Overhead usage"):
        load_overhead(path)
