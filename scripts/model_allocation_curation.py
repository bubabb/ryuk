"""Validate and compile sealed v3 model-allocation curation manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_allocation_manifest import validate_manifest

EXPECTED_STRATA = {
    "bounded_evidence_and_documentation": 15,
    "scoped_implementation": 35,
    "security_and_tenant_boundaries": 15,
    "concurrency_and_recovery": 15,
    "architecture_and_evaluation": 20,
}
ALLOWED_MODELS = {"gpt-6-luna", "gpt-6-sol", "gpt-6-astra"}
ALLOWED_EFFORTS = {"low", "medium", "high"}
SHA256_LENGTH = 64
GIT_SHA1_LENGTH = 40


def _exact_fields(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields must be exactly {sorted(expected)}")


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value


def _sha256(value: Any, name: str) -> str:
    text = _nonblank(value, name)
    if len(text) != SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 value")
    return text


def _git_commit(value: Any) -> str:
    text = _nonblank(value, "baseline_commit")
    if len(text) != GIT_SHA1_LENGTH or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError("baseline_commit must be a full lowercase Git SHA-1")
    return text


def _validate_curation(curation: Any) -> None:
    if not isinstance(curation, dict):
        raise ValueError("curation must be an object")
    _exact_fields(
        curation,
        {
            "curator_id",
            "candidate_author_ids",
            "independent_from_candidate_authors",
            "completed_before_candidate_access",
            "blind_to_arm_outcomes",
            "selection_method",
            "sampling_frame_sha256",
        },
        "curation",
    )
    curator = _nonblank(curation.get("curator_id"), "curator_id")
    authors = curation.get("candidate_author_ids")
    if (
        not isinstance(authors, list)
        or not authors
        or any(not isinstance(author, str) or not author.strip() for author in authors)
        or len(set(authors)) != len(authors)
    ):
        raise ValueError("candidate_author_ids must be unique nonblank strings")
    if curator in authors:
        raise ValueError("curator_id must differ from every candidate author")
    for field in (
        "independent_from_candidate_authors",
        "completed_before_candidate_access",
        "blind_to_arm_outcomes",
    ):
        if curation.get(field) is not True:
            raise ValueError(f"curation.{field} must be true")
    _nonblank(curation.get("selection_method"), "selection_method")
    _sha256(curation.get("sampling_frame_sha256"), "sampling_frame_sha256")


def _validate_case(case: Any, seen: set[str]) -> None:
    if not isinstance(case, dict):
        raise ValueError("Every case must be an object")
    _exact_fields(
        case,
        {
            "id",
            "stratum",
            "category",
            "prompt",
            "critical",
            "source",
            "holdout",
            "grading",
            "allocation",
        },
        "case",
    )
    case_id = _nonblank(case.get("id"), "case.id")
    if case_id in seen:
        raise ValueError(f"Duplicate case id: {case_id}")
    seen.add(case_id)
    if case.get("stratum") not in EXPECTED_STRATA:
        raise ValueError(f"Case {case_id} has an unknown stratum")
    _nonblank(case.get("category"), f"{case_id}.category")
    _nonblank(case.get("prompt"), f"{case_id}.prompt")
    if type(case.get("critical")) is not bool:
        raise ValueError(f"{case_id}.critical must be boolean")

    source = case.get("source")
    if not isinstance(source, dict) or source.get("kind") not in {
        "synthetic",
        "public",
    }:
        raise ValueError(f"{case_id}.source must be synthetic or public")
    _exact_fields(source, {"kind", "reference", "content_sha256"}, "source")
    _nonblank(source.get("reference"), f"{case_id}.source.reference")
    _sha256(source.get("content_sha256"), f"{case_id}.source.content_sha256")

    holdout = case.get("holdout")
    if not isinstance(holdout, dict) or any(
        holdout.get(field) is not True
        for field in (
            "absent_from_v1_v2",
            "absent_from_candidate_examples",
            "unseen_by_candidate_authors",
        )
    ):
        raise ValueError(f"{case_id} must carry all holdout attestations")
    _exact_fields(
        holdout,
        {
            "absent_from_v1_v2",
            "absent_from_candidate_examples",
            "unseen_by_candidate_authors",
        },
        "holdout",
    )

    grading = case.get("grading")
    if not isinstance(grading, dict):
        raise ValueError(f"{case_id}.grading must be an object")
    if len(grading) != 1 or not set(grading) <= {
        "expected",
        "checks",
        "review_criteria",
    }:
        raise ValueError(f"{case_id} must declare exactly one grading mode")
    expected = grading.get("expected")
    checks = grading.get("checks")
    criteria = grading.get("review_criteria")
    modes = sum(
        (
            expected is not None,
            isinstance(checks, list) and bool(checks),
            isinstance(criteria, list) and bool(criteria),
        )
    )
    if modes != 1:
        raise ValueError(f"{case_id} must declare exactly one grading mode")
    for name, values in (("checks", checks), ("review_criteria", criteria)):
        if values is not None and (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise ValueError(f"{case_id}.{name} must contain nonblank strings")

    allocation = case.get("allocation")
    if not isinstance(allocation, dict):
        raise ValueError(f"{case_id}.allocation must be an object")
    _exact_fields(allocation, {"model", "effort"}, "allocation")
    if allocation.get("model") not in ALLOWED_MODELS:
        raise ValueError(f"{case_id} has an unsupported allocation model")
    if allocation.get("effort") not in ALLOWED_EFFORTS:
        raise ValueError(f"{case_id} has an unsupported allocation effort")


def validate_curation_manifest(document: dict[str, Any]) -> None:
    """Enforce the preregistered sample and sealed-case curation contract."""

    _exact_fields(
        document,
        {"version", "purpose", "baseline_commit", "curation", "cases"},
        "manifest",
    )
    if document.get("version") != 3:
        raise ValueError("Curation manifest version must be 3")
    _nonblank(document.get("purpose"), "purpose")
    _git_commit(document.get("baseline_commit"))
    _validate_curation(document.get("curation"))
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 100:
        raise ValueError("Curation manifest must contain exactly 100 cases")
    seen: set[str] = set()
    for case in cases:
        _validate_case(case, seen)
    observed = {
        stratum: sum(case["stratum"] == stratum for case in cases)
        for stratum in EXPECTED_STRATA
    }
    if observed != EXPECTED_STRATA:
        raise ValueError("Case strata do not match the preregistered distribution")


def compile_execution_manifest(document: dict[str, Any]) -> dict[str, Any]:
    """Expand one validated case record into two identical matched-arm tasks."""

    validate_curation_manifest(document)
    tasks: list[dict[str, Any]] = []
    for case in document["cases"]:
        grading = case["grading"]
        shared = {
            "case_id": case["id"],
            "category": case["category"],
            "prompt": case["prompt"],
            "expected": grading.get("expected"),
            "checks": grading.get("checks"),
            "review_criteria": grading.get("review_criteria"),
            "critical": case["critical"],
            "stratum": case["stratum"],
            "source": case["source"],
        }
        for arm, assignment in (
            ("allocation", case["allocation"]),
            ("all_astra_baseline", {"model": "gpt-6-astra", "effort": "high"}),
        ):
            tasks.append(
                {
                    **shared,
                    "id": f"{case['id']}--{arm}",
                    "arm": arm,
                    **assignment,
                }
            )
    manifest = {
        "version": 3,
        "baseline_commit": document["baseline_commit"],
        "purpose": document["purpose"],
        "threshold": {
            "planned_tasks": 200,
            "minimum_first_pass": 94,
            "critical_failures_allowed": 0,
        },
        "comparison": {
            "arms": ["allocation", "all_astra_baseline"],
            "baseline_arm": "all_astra_baseline",
            "require_complete_pairs": True,
        },
        "review": {
            "require_independent": True,
            "candidate_author_ids": document["curation"]["candidate_author_ids"],
            "blind_to_arm_until_scores_are_frozen": True,
        },
        "resume_policy": {
            "retry_statuses": [],
            "maximum_infrastructure_attempts_per_task": 1,
            "quality_failures_retryable": False,
        },
        "curation_sha256": hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "tasks": tasks,
    }
    validate_manifest(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Print the expanded execution manifest after validation",
    )
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text())
    validate_curation_manifest(document)
    if args.compile:
        print(json.dumps(compile_execution_manifest(document), indent=2))
    else:
        print("Valid v3 curation manifest: 100 held-out cases; no model calls")


if __name__ == "__main__":
    main()
