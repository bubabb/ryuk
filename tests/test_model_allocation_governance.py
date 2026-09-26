import copy
import hashlib
import json

import pytest

from scripts.evaluate_model_allocation import authorize_manifest_run
from scripts.model_allocation_governance import (
    load_governance,
    minimum_passes,
    validate_governance,
    wilson_lower,
)


def governance_path():
    from scripts.evaluate_model_allocation import ROOT

    return ROOT / "evals/model_allocation/v3-governance.json"


def test_governance_is_valid_but_blocked_by_named_readiness_evidence():
    document, blockers = load_governance(governance_path())
    assert blockers == tuple(
        field for field, value in document["readiness"].items() if value is None
    )
    assert document["status"] == "blocked"
    assert minimum_passes(100, 0.87) == 94
    assert wilson_lower(94, 100) > 0.87
    assert wilson_lower(93, 100) < 0.87


def test_governance_metric_hash_matches_reviewed_implementation():
    document, _ = load_governance(governance_path())
    implementation = (
        governance_path().parents[2] / "scripts/model_allocation_statistics.py"
    )
    digest = hashlib.sha256(implementation.read_bytes()).hexdigest()
    assert document["readiness"]["paired_metric_implementation_sha256"] == digest


@pytest.mark.parametrize(
    "mutation,message",
    [
        (("sample", "planned_calls", 199), "planned_calls"),
        (("quality_gate", "minimum_allocation_passes", 93), "Wilson"),
        (("sample", "held_out_from_candidates", False), "held-out"),
        (("savings_gate", "require_applicable_billing_snapshot", False), "Savings"),
        (("review", "independent_required", False), "review"),
        (("quality_gate", "noninferiority_margin", False), "Quality"),
    ],
)
def test_governance_rejects_weakened_or_inconsistent_policy(mutation, message):
    document, _ = load_governance(governance_path())
    changed = copy.deepcopy(document)
    section, field, value = mutation
    changed[section][field] = value
    with pytest.raises(ValueError, match=message):
        validate_governance(changed)


def test_v3_runner_refuses_blocked_or_wrong_manifest_governance(tmp_path):
    manifest = {"version": 3}
    digest = "a" * 64
    with pytest.raises(ValueError, match="require a governance"):
        authorize_manifest_run(manifest, digest, None)
    with pytest.raises(ValueError, match="incomplete governance"):
        authorize_manifest_run(manifest, digest, governance_path())

    document, _ = load_governance(governance_path())
    ready = copy.deepcopy(document)
    ready["status"] = "ready"
    for field in ready["readiness"]:
        ready["readiness"][field] = "recorded"
    ready["readiness"]["curator_id"] = "curator"
    ready["readiness"]["reviewer_id"] = "reviewer"
    ready["readiness"]["case_manifest_sha256"] = "b" * 64
    ready["readiness"]["paired_metric_implementation_sha256"] = "c" * 64
    record = tmp_path / "ready.json"
    record.write_text(json.dumps(ready))
    with pytest.raises(ValueError, match="not bound"):
        authorize_manifest_run(manifest, digest, record)
    ready["readiness"]["case_manifest_sha256"] = digest
    record.write_text(json.dumps(ready))
    authorize_manifest_run(manifest, digest, record)


def test_ready_governance_requires_distinct_roles_and_real_hashes():
    document, _ = load_governance(governance_path())
    ready = copy.deepcopy(document)
    ready["status"] = "ready"
    for field in ready["readiness"]:
        ready["readiness"][field] = "recorded"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_governance(ready)
    ready["readiness"]["case_manifest_sha256"] = "a" * 64
    ready["readiness"]["paired_metric_implementation_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="must differ"):
        validate_governance(ready)


def test_recorded_metric_hash_must_be_a_real_hash_while_blocked():
    document, _ = load_governance(governance_path())
    changed = copy.deepcopy(document)
    changed["readiness"]["paired_metric_implementation_sha256"] = "recorded"
    with pytest.raises(ValueError, match="metric hash"):
        validate_governance(changed)
