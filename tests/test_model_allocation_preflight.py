import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.evaluate_model_allocation import authorize_manifest_run
from scripts.model_allocation_curation import (
    EXPECTED_STRATA,
    compile_execution_manifest,
)
from scripts.model_allocation_evidence import file_sha256, response_set_sha256
from scripts.model_allocation_governance import load_governance
from scripts.model_allocation_manifest import load_manifest
from scripts.model_allocation_preflight import (
    governance_policy_sha256,
    validate_readiness_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def curation_document():
    cases = []
    index = 0
    for stratum, count in EXPECTED_STRATA.items():
        for _ in range(count):
            index += 1
            source = f"preflight-fixture-{index}"
            cases.append(
                {
                    "id": f"V3-C{index:03}",
                    "stratum": stratum,
                    "category": "preflight-fixture",
                    "prompt": f"Return fixture value {index}",
                    "critical": stratum == "security_and_tenant_boundaries",
                    "source": {
                        "kind": "synthetic",
                        "reference": source,
                        "content_sha256": hashlib.sha256(source.encode()).hexdigest(),
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
        "purpose": "Synthetic preflight fixture; not an evaluation",
        "baseline_commit": "a" * 40,
        "curation": {
            "curator_id": "curator-fixture",
            "candidate_author_ids": ["candidate-fixture"],
            "independent_from_candidate_authors": True,
            "completed_before_candidate_access": True,
            "blind_to_arm_outcomes": True,
            "selection_method": "synthetic test generation",
            "sampling_frame_sha256": "b" * 64,
        },
        "cases": cases,
    }


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build_pre_run_bundle(tmp_path):
    curation = curation_document()
    curation_path = tmp_path / "curation.json"
    manifest_path = tmp_path / "manifest.json"
    write_json(curation_path, curation)
    write_json(manifest_path, compile_execution_manifest(curation))
    manifest, manifest_digest = load_manifest(manifest_path)

    governance, _ = load_governance(
        ROOT / "evals/model_allocation/v3-governance.json"
    )
    governance = copy.deepcopy(governance)
    governance["status"] = "ready"
    governance["readiness"].update(
        {
            "case_manifest_sha256": manifest_digest,
            "curator_id": "curator-fixture",
            "reviewer_id": "reviewer-fixture",
            "billing_snapshot_id": "billing-fixture",
            "model_access_probe_id": "access-fixture",
            "owner_run_approval_id": "approval-fixture",
        }
    )
    governance_path = tmp_path / "governance.json"
    write_json(governance_path, governance)

    rate = {
        "input_usd_per_million_tokens": "1",
        "cached_input_usd_per_million_tokens": "0.5",
        "output_usd_per_million_tokens": "5",
    }
    billing = {
        "id": "billing-fixture",
        "captured_at": "2026-09-26T09:00:00+00:00",
        "currency": "USD",
        "source_reference": "synthetic billing fixture",
        "applicable_to_run": True,
        "reasoning_output_billed_separately": False,
        "model_rates": {"gpt-6-sol": rate, "gpt-6-astra": rate},
    }
    billing_path = tmp_path / "billing.json"
    write_json(billing_path, billing)

    assignments = sorted(
        {(task["model"], task["effort"]) for task in manifest["tasks"]}
    )
    access = {
        "version": 1,
        "id": "access-fixture",
        "manifest_sha256": manifest_digest,
        "observed_at": "2026-09-26T09:01:00+00:00",
        "environment_id": "synthetic-environment",
        "successful": True,
        "assignments": [
            {"model": model, "effort": effort} for model, effort in assignments
        ],
        "evidence_sha256": "c" * 64,
    }
    access_path = tmp_path / "access.json"
    write_json(access_path, access)

    approval = {
        "version": 1,
        "id": "approval-fixture",
        "approved": True,
        "approved_at": "2026-09-26T09:02:00+00:00",
        "approver_id": "owner-fixture",
        "manifest_sha256": manifest_digest,
        "governance_policy_sha256": governance_policy_sha256(governance),
        "access_probe_id": "access-fixture",
        "billing_snapshot_id": "billing-fixture",
        "maximum_calls": 200,
        "synthetic_or_public_only": True,
    }
    approval_path = tmp_path / "approval.json"
    write_json(approval_path, approval)

    bundle = {
        "version": 1,
        "phase": "pre_run",
        "artifacts": {
            "governance": "governance.json",
            "curation_manifest": "curation.json",
            "execution_manifest": "manifest.json",
            "billing_snapshot": "billing.json",
            "access_probe": "access.json",
            "owner_approval": "approval.json",
            "run_directory": None,
            "review_ledger": None,
            "savings_evidence": None,
        },
    }
    bundle_path = tmp_path / "bundle.json"
    write_json(bundle_path, bundle)
    return bundle_path, manifest_path


def test_pre_run_bundle_cross_binds_every_authorization_receipt(tmp_path):
    bundle_path, manifest_path = build_pre_run_bundle(tmp_path)
    report = validate_readiness_bundle(
        bundle_path, expected_manifest_path=manifest_path
    )
    assert report["phase"] == "pre_run"
    assert report["pre_run_authorized"] is True
    assert report["post_run_evidence_valid"] is False
    assert report["external_evidence_claimed_not_proven"] is True
    manifest, digest = load_manifest(manifest_path)
    authorize_manifest_run(
        manifest,
        digest,
        tmp_path / "governance.json",
        bundle_path,
        manifest_path,
    )


def test_bundle_paths_cannot_escape_the_bundle_directory(tmp_path):
    bundle_path, _ = build_pre_run_bundle(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    bundle["artifacts"]["access_probe"] = "../access.json"
    write_json(bundle_path, bundle)
    with pytest.raises(ValueError, match="stay inside"):
        validate_readiness_bundle(bundle_path)


def test_preflight_rejects_incomplete_access_probe(tmp_path):
    bundle_path, _ = build_pre_run_bundle(tmp_path)
    access_path = tmp_path / "access.json"
    access = json.loads(access_path.read_text())
    access["assignments"].pop()
    write_json(access_path, access)
    with pytest.raises(ValueError, match="assignments do not match"):
        validate_readiness_bundle(bundle_path)


def test_preflight_rejects_owner_approval_for_different_policy(tmp_path):
    bundle_path, _ = build_pre_run_bundle(tmp_path)
    approval_path = tmp_path / "approval.json"
    approval = json.loads(approval_path.read_text())
    approval["governance_policy_sha256"] = "f" * 64
    write_json(approval_path, approval)
    with pytest.raises(ValueError, match="governance policy"):
        validate_readiness_bundle(bundle_path)


def test_preflight_rejects_approval_before_prerequisite_evidence(tmp_path):
    bundle_path, _ = build_pre_run_bundle(tmp_path)
    approval_path = tmp_path / "approval.json"
    approval = json.loads(approval_path.read_text())
    approval["approved_at"] = "2026-09-26T08:59:00+00:00"
    write_json(approval_path, approval)
    with pytest.raises(ValueError, match="cannot precede"):
        validate_readiness_bundle(bundle_path)


def test_preflight_rejects_governance_strings_without_complete_evidence(tmp_path):
    bundle_path, _ = build_pre_run_bundle(tmp_path)
    governance_path = tmp_path / "governance.json"
    governance = json.loads(governance_path.read_text())
    governance["status"] = "blocked"
    governance["readiness"]["owner_run_approval_id"] = None
    write_json(governance_path, governance)
    with pytest.raises(ValueError, match="governance is incomplete"):
        validate_readiness_bundle(bundle_path)


def test_post_run_bundle_binds_measurements_responses_review_and_savings(tmp_path):
    bundle_path, manifest_path = build_pre_run_bundle(tmp_path)
    manifest, manifest_digest = load_manifest(manifest_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    run_file = run_directory / "run.json"
    write_json(run_file, {"manifest_sha256": manifest_digest})
    sample_usage = {
        "input_tokens": 10,
        "cached_input_tokens": 2,
        "output_tokens": 3,
        "reasoning_output_tokens": 1,
    }
    for task in manifest["tasks"]:
        folder = run_directory / task["id"]
        folder.mkdir()
        write_json(folder / "response.json", {"content": '{"fixture":true}'})
        write_json(
            folder / "measurement.json",
            {
                "id": task["id"],
                "status": "completed",
                "model_requested": task["model"],
                "effort": task["effort"],
                "usage": sample_usage,
            },
        )
    empty_alias_digest = hashlib.sha256(b"[]").hexdigest()
    review = {
        "version": 1,
        "manifest_sha256": manifest_digest,
        "run_sha256": file_sha256(run_file),
        "response_set_sha256": response_set_sha256(manifest, run_directory),
        "reviewer_id": "reviewer-fixture",
        "candidate_author_ids": ["candidate-fixture"],
        "independent": True,
        "blinding": {
            "alias_map_sha256": empty_alias_digest,
            "arm_labels_hidden_until_scores_frozen": True,
            "scores_frozen_at": "2026-09-26T10:00:00+00:00",
            "unblinded_at": "2026-09-26T10:01:00+00:00",
        },
        "reviews": [],
    }
    review_path = tmp_path / "review.json"
    write_json(review_path, review)
    billing = json.loads((tmp_path / "billing.json").read_text())
    overhead = [
        {
            "arm": arm,
            "category": category,
            "model": "gpt-6-sol" if arm == "allocation" else "gpt-6-astra",
            "usage": sample_usage,
        }
        for arm in ("allocation", "all_astra_baseline")
        for category in ("setup", "grading", "review")
    ]
    savings = {
        "version": 1,
        "manifest_sha256": manifest_digest,
        "run_sha256": file_sha256(run_file),
        "review_ledger_sha256": file_sha256(review_path),
        "billing_snapshot": billing,
        "overhead": overhead,
    }
    savings_path = tmp_path / "savings.json"
    write_json(savings_path, savings)
    bundle = json.loads(bundle_path.read_text())
    bundle["phase"] = "post_run"
    bundle["artifacts"].update(
        {
            "run_directory": "run",
            "review_ledger": "review.json",
            "savings_evidence": "savings.json",
        }
    )
    write_json(bundle_path, bundle)
    report = validate_readiness_bundle(bundle_path)
    assert report["post_run_evidence_valid"] is True

    first = run_directory / manifest["tasks"][0]["id"] / "measurement.json"
    measurement = json.loads(first.read_text())
    measurement["usage"] = None
    write_json(first, measurement)
    with pytest.raises(ValueError, match="four token counters"):
        validate_readiness_bundle(bundle_path)
