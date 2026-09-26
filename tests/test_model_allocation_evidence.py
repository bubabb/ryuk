import copy
import hashlib
import json

import pytest

from scripts.model_allocation_evidence import (
    compile_review_for_grader,
    evaluate_savings,
    validate_blinded_review_ledger,
    validate_savings_evidence,
)

MANIFEST_DIGEST = "a" * 64
RUN_DIGEST = "b" * 64
REVIEW_DIGEST = "c" * 64


def manifest():
    return {
        "review": {
            "require_independent": True,
            "candidate_author_ids": ["candidate-fixture"],
        },
        "tasks": [
            {
                "id": "V3-C001--allocation",
                "expected": None,
            },
            {
                "id": "V3-C001--all_astra_baseline",
                "expected": None,
            },
            {
                "id": "V3-C002--allocation",
                "expected": {"value": 2},
            },
            {
                "id": "V3-C002--all_astra_baseline",
                "expected": {"value": 2},
            },
        ],
    }


def review_ledger():
    reviews = [
        {
            "blind_id": "B001",
            "task_id": "V3-C001--allocation",
            "response_sha256": "d" * 64,
            "verdict": "pass",
            "notes": "fixture criterion satisfied",
        },
        {
            "blind_id": "B002",
            "task_id": "V3-C001--all_astra_baseline",
            "response_sha256": "e" * 64,
            "verdict": "fail",
            "notes": "fixture criterion not satisfied",
        },
    ]
    alias_map = [
        {"blind_id": item["blind_id"], "task_id": item["task_id"]}
        for item in reviews
    ]
    alias_digest = hashlib.sha256(
        json.dumps(alias_map, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "version": 1,
        "manifest_sha256": MANIFEST_DIGEST,
        "run_sha256": RUN_DIGEST,
        "response_set_sha256": "f" * 64,
        "reviewer_id": "reviewer-fixture",
        "candidate_author_ids": ["candidate-fixture"],
        "independent": True,
        "blinding": {
            "alias_map_sha256": alias_digest,
            "arm_labels_hidden_until_scores_frozen": True,
            "scores_frozen_at": "2026-09-26T10:00:00+00:00",
            "unblinded_at": "2026-09-26T10:01:00+00:00",
        },
        "reviews": reviews,
    }


def usage(input_tokens=100, cached_input_tokens=0, output_tokens=10):
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": 2,
    }


def savings_evidence():
    overhead = [
        {
            "arm": arm,
            "category": category,
            "model": "gpt-6-sol" if arm == "allocation" else "gpt-6-astra",
            "usage": usage(10, 0, 1),
        }
        for arm in ("allocation", "all_astra_baseline")
        for category in ("setup", "grading", "review")
    ]
    return {
        "version": 1,
        "manifest_sha256": MANIFEST_DIGEST,
        "run_sha256": RUN_DIGEST,
        "review_ledger_sha256": REVIEW_DIGEST,
        "billing_snapshot": {
            "id": "billing-fixture",
            "captured_at": "2026-09-26T09:00:00+00:00",
            "currency": "USD",
            "source_reference": "synthetic rate fixture",
            "applicable_to_run": True,
            "reasoning_output_billed_separately": False,
            "model_rates": {
                "gpt-6-sol": {
                    "input_usd_per_million_tokens": "2",
                    "cached_input_usd_per_million_tokens": "1",
                    "output_usd_per_million_tokens": "10",
                },
                "gpt-6-astra": {
                    "input_usd_per_million_tokens": "10",
                    "cached_input_usd_per_million_tokens": "5",
                    "output_usd_per_million_tokens": "50",
                },
            },
        },
        "overhead": overhead,
    }


def validate_review(document):
    validate_blinded_review_ledger(
        document,
        manifest(),
        manifest_sha256=MANIFEST_DIGEST,
        run_sha256=RUN_DIGEST,
    )


def validate_savings(document):
    validate_savings_evidence(
        document,
        manifest_sha256=MANIFEST_DIGEST,
        run_sha256=RUN_DIGEST,
        review_ledger_sha256=REVIEW_DIGEST,
        billing_snapshot_id="billing-fixture",
    )


def test_blinded_review_validates_and_compiles_for_grader():
    document = review_ledger()
    validate_review(document)
    compiled = compile_review_for_grader(document)
    assert compiled["_meta"]["reviewer_id"] == "reviewer-fixture"
    assert compiled["V3-C001--allocation"]["pass"] is True
    assert compiled["V3-C001--all_astra_baseline"]["pass"] is False


def test_blinded_review_binds_every_response_file(tmp_path):
    document = review_ledger()
    review_by_task = {item["task_id"]: item for item in document["reviews"]}
    response_bindings = []
    for task in manifest()["tasks"]:
        folder = tmp_path / task["id"]
        folder.mkdir()
        response = folder / "response.json"
        response.write_text(json.dumps({"content": task["id"]}))
        digest = hashlib.sha256(response.read_bytes()).hexdigest()
        response_bindings.append({"task_id": task["id"], "response_sha256": digest})
        if task["id"] in review_by_task:
            review_by_task[task["id"]]["response_sha256"] = digest
    document["response_set_sha256"] = hashlib.sha256(
        json.dumps(
            sorted(response_bindings, key=lambda item: item["task_id"]),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    validate_blinded_review_ledger(
        document,
        manifest(),
        manifest_sha256=MANIFEST_DIGEST,
        run_sha256=RUN_DIGEST,
        response_directory=tmp_path,
    )
    (tmp_path / document["reviews"][0]["task_id"] / "response.json").write_text(
        json.dumps({"content": "changed"})
    )
    with pytest.raises(ValueError, match="response.*hash mismatch"):
        validate_blinded_review_ledger(
            document,
            manifest(),
            manifest_sha256=MANIFEST_DIGEST,
            run_sha256=RUN_DIGEST,
            response_directory=tmp_path,
        )


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda value: value.update(run_sha256="f" * 64), "not bound"),
        (
            lambda value: value.update(reviewer_id="candidate-fixture"),
            "independent",
        ),
        (
            lambda value: value["blinding"].update(
                unblinded_at="2026-09-26T09:59:00+00:00"
            ),
            "must occur after",
        ),
        (lambda value: value["reviews"].pop(), "cover every"),
        (
            lambda value: value["blinding"].update(alias_map_sha256="f" * 64),
            "hash mismatch",
        ),
    ],
)
def test_blinded_review_fails_closed(mutation, message):
    document = copy.deepcopy(review_ledger())
    mutation(document)
    with pytest.raises(ValueError, match=message):
        validate_review(document)


def test_savings_recomputes_all_in_cost_and_requires_quality_first():
    document = savings_evidence()
    validate_savings(document)
    results = [
        {
            "arm": "allocation",
            "model": "gpt-6-sol",
            "usage": usage(),
        },
        {
            "arm": "all_astra_baseline",
            "model": "gpt-6-astra",
            "usage": usage(),
        },
    ]
    passed = evaluate_savings(
        results,
        document,
        quality_gate_passed=True,
        minimum_cost_reduction=0.25,
    )
    assert passed["cost_reduction"] == "0.8"
    assert passed["passed"] is True
    blocked = evaluate_savings(
        results,
        document,
        quality_gate_passed=False,
        minimum_cost_reduction=0.25,
    )
    assert blocked["passed"] is False


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda value: value.update(manifest_sha256="f" * 64), "binding"),
        (lambda value: value["overhead"].pop(), "setup, grading"),
        (
            lambda value: value["overhead"][0]["usage"].update(
                cached_input_tokens=11
            ),
            "cannot exceed",
        ),
        (
            lambda value: value["billing_snapshot"].update(
                applicable_to_run=False
            ),
            "applicable USD",
        ),
        (
            lambda value: value["billing_snapshot"]["model_rates"][
                "gpt-6-sol"
            ].update(input_usd_per_million_tokens="unknown"),
            "decimal string",
        ),
        (
            lambda value: value["billing_snapshot"]["model_rates"][
                "gpt-6-sol"
            ].update(input_usd_per_million_tokens="1E2"),
            "decimal string",
        ),
    ],
)
def test_savings_evidence_fails_closed(mutation, message):
    document = copy.deepcopy(savings_evidence())
    mutation(document)
    with pytest.raises(ValueError, match=message):
        validate_savings(document)


def test_savings_rejects_missing_candidate_usage():
    document = savings_evidence()
    validate_savings(document)
    with pytest.raises(ValueError, match="four token counters"):
        evaluate_savings(
            [
                {
                    "arm": "allocation",
                    "model": "gpt-6-sol",
                    "usage": None,
                }
            ],
            document,
            quality_gate_passed=True,
            minimum_cost_reduction=0.25,
        )
