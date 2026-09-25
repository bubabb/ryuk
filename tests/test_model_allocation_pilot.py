import hashlib
import json

import pytest

from scripts.evaluate_model_allocation import PILOT, prompt_for
from scripts.grade_model_allocation import grade_task, summarize, wilson


def test_manifest_is_complete_and_candidate_prompt_hides_grading():
    manifest = json.loads(PILOT.read_text())
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
