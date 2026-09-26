import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.model_allocation_curation import (
    EXPECTED_STRATA,
    compile_execution_manifest,
    validate_curation_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def curation_manifest():
    cases = []
    index = 0
    for stratum, count in EXPECTED_STRATA.items():
        for _ in range(count):
            index += 1
            cases.append(
                {
                    "id": f"V3-C{index:03}",
                    "stratum": stratum,
                    "category": "synthetic-test-category",
                    "prompt": f"Return synthetic result {index}",
                    "critical": stratum == "security_and_tenant_boundaries",
                    "source": {
                        "kind": "synthetic",
                        "reference": f"fixture-{index}",
                        "content_sha256": hashlib.sha256(
                            f"fixture-{index}".encode()
                        ).hexdigest(),
                    },
                    "holdout": {
                        "absent_from_v1_v2": True,
                        "absent_from_candidate_examples": True,
                        "unseen_by_candidate_authors": True,
                    },
                    "grading": {"expected": {"value": index}},
                    "allocation": {"model": "gpt-6-sol", "effort": "high"},
                }
            )
    return {
        "version": 3,
        "purpose": "Synthetic test fixture; never a real evaluation manifest",
        "baseline_commit": "a" * 40,
        "curation": {
            "curator_id": "curator-fixture",
            "candidate_author_ids": ["candidate-fixture"],
            "independent_from_candidate_authors": True,
            "completed_before_candidate_access": True,
            "blind_to_arm_outcomes": True,
            "selection_method": "deterministic synthetic test construction",
            "sampling_frame_sha256": "b" * 64,
        },
        "cases": cases,
    }


def test_schema_is_a_template_and_contains_no_cases():
    schema = json.loads(
        (ROOT / "evals/model_allocation/v3-case-manifest.schema.json").read_text()
    )
    assert schema["properties"]["cases"]["minItems"] == 100
    assert schema["properties"]["cases"]["maxItems"] == 100
    assert "examples" not in schema


def test_compiler_expands_exactly_identical_matched_pairs():
    document = curation_manifest()
    validate_curation_manifest(document)
    manifest = compile_execution_manifest(document)
    assert len(manifest["tasks"]) == 200
    assert len(manifest["curation_sha256"]) == 64
    assert manifest["review"] == {
        "require_independent": True,
        "candidate_author_ids": ["candidate-fixture"],
        "blind_to_arm_until_scores_are_frozen": True,
    }
    for index in range(0, 200, 2):
        allocation, baseline = manifest["tasks"][index : index + 2]
        assert allocation["arm"] == "allocation"
        assert baseline["arm"] == "all_astra_baseline"
        assert (baseline["model"], baseline["effort"]) == (
            "gpt-6-astra",
            "high",
        )
        differing = {
            key
            for key in allocation | baseline
            if allocation.get(key) != baseline.get(key)
        }
        assert differing == {"id", "arm", "model"}


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda doc: doc["cases"].pop(), "exactly 100"),
        (lambda doc: doc["cases"][1].update(id="V3-C001"), "Duplicate"),
        (
            lambda doc: doc["cases"][0].update(stratum="unknown"),
            "unknown stratum",
        ),
        (
            lambda doc: doc["cases"][0]["source"].update(kind="private"),
            "synthetic or public",
        ),
        (
            lambda doc: doc["cases"][0]["holdout"].update(
                unseen_by_candidate_authors=False
            ),
            "holdout attestations",
        ),
        (
            lambda doc: doc["cases"][0]["grading"].update(checks=["assert"]),
            "exactly one grading mode",
        ),
        (
            lambda doc: doc["curation"].update(curator_id="candidate-fixture"),
            "must differ",
        ),
    ],
)
def test_validator_rejects_curation_leakage_and_protocol_drift(mutate, message):
    document = copy.deepcopy(curation_manifest())
    mutate(document)
    with pytest.raises(ValueError, match=message):
        validate_curation_manifest(document)
