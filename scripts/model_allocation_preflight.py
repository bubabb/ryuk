"""Cross-bind v3 evaluation evidence and emit a deterministic preflight report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_allocation_curation import (  # noqa: E402
    compile_execution_manifest,
    validate_curation_manifest,
)
from scripts.model_allocation_evidence import (  # noqa: E402
    file_sha256,
    validate_blinded_review_ledger,
    validate_candidate_measurements,
    validate_savings_evidence,
)
from scripts.model_allocation_governance import load_governance  # noqa: E402
from scripts.model_allocation_manifest import load_manifest  # noqa: E402

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RATE_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")


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


def _time(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as failure:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from failure
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def governance_policy_sha256(governance: dict[str, Any]) -> str:
    """Hash policy and prerequisite evidence without the circular approval ID."""

    policy = json.loads(json.dumps(governance))
    policy["status"] = "blocked"
    policy["readiness"]["owner_run_approval_id"] = None
    return hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_billing_snapshot(document: dict[str, Any], expected_id: str) -> None:
    _exact(
        document,
        {
            "id",
            "captured_at",
            "currency",
            "source_reference",
            "applicable_to_run",
            "reasoning_output_billed_separately",
            "model_rates",
        },
        "billing snapshot",
    )
    if _text(document["id"], "billing id") != expected_id:
        raise ValueError("Billing snapshot ID differs from governance")
    _time(document["captured_at"], "billing captured_at")
    if document["currency"] != "USD" or document["applicable_to_run"] is not True:
        raise ValueError("Billing snapshot must be applicable USD evidence")
    if document["reasoning_output_billed_separately"] is not False:
        raise ValueError("Reasoning output must be included in output billing")
    _text(document["source_reference"], "billing source reference")
    rates = document["model_rates"]
    if not isinstance(rates, dict) or not rates:
        raise ValueError("Billing snapshot needs model rates")
    rate_fields = {
        "input_usd_per_million_tokens",
        "cached_input_usd_per_million_tokens",
        "output_usd_per_million_tokens",
    }
    for model, rate in rates.items():
        _text(model, "billing model")
        if not isinstance(rate, dict):
            raise ValueError("Every model rate must be an object")
        _exact(rate, rate_fields, "model rate")
        for value in rate.values():
            if not isinstance(value, str) or RATE_RE.fullmatch(value) is None:
                raise ValueError("Billing rates must be nonnegative decimal strings")
            try:
                parsed = Decimal(value)
            except InvalidOperation as failure:
                raise ValueError("Billing rate is invalid") from failure
            if not parsed.is_finite() or parsed < 0:
                raise ValueError("Billing rate is invalid")


def validate_access_probe(
    document: dict[str, Any],
    *,
    expected_id: str,
    manifest_sha256: str,
    required_assignments: set[tuple[str, str]],
) -> None:
    _exact(
        document,
        {
            "version",
            "id",
            "manifest_sha256",
            "observed_at",
            "environment_id",
            "successful",
            "assignments",
            "evidence_sha256",
        },
        "access probe",
    )
    if document["version"] != 1 or document["successful"] is not True:
        raise ValueError("Access probe must record a successful version 1 probe")
    if _text(document["id"], "access probe id") != expected_id:
        raise ValueError("Access probe ID differs from governance")
    if _sha(document["manifest_sha256"], "manifest_sha256") != manifest_sha256:
        raise ValueError("Access probe is not bound to this manifest")
    _time(document["observed_at"], "access observed_at")
    _text(document["environment_id"], "environment_id")
    _sha(document["evidence_sha256"], "access evidence_sha256")
    assignments = document["assignments"]
    if not isinstance(assignments, list):
        raise ValueError("Access assignments must be a list")
    observed: set[tuple[str, str]] = set()
    for item in assignments:
        if not isinstance(item, dict):
            raise ValueError("Access assignment must be an object")
        _exact(item, {"model", "effort"}, "access assignment")
        observed.add(
            (_text(item["model"], "model"), _text(item["effort"], "effort"))
        )
    if len(observed) != len(assignments) or observed != required_assignments:
        raise ValueError("Access probe assignments do not match the manifest")


def validate_owner_approval(
    document: dict[str, Any],
    *,
    expected_id: str,
    manifest_sha256: str,
    policy_sha256: str,
    access_probe_id: str,
    billing_snapshot_id: str,
    planned_calls: int,
) -> None:
    _exact(
        document,
        {
            "version",
            "id",
            "approved",
            "approved_at",
            "approver_id",
            "manifest_sha256",
            "governance_policy_sha256",
            "access_probe_id",
            "billing_snapshot_id",
            "maximum_calls",
            "synthetic_or_public_only",
        },
        "owner approval",
    )
    if document["version"] != 1 or document["approved"] is not True:
        raise ValueError("Owner approval must be an approved version 1 receipt")
    if _text(document["id"], "approval id") != expected_id:
        raise ValueError("Owner approval ID differs from governance")
    _text(document["approver_id"], "approver_id")
    _time(document["approved_at"], "approved_at")
    if _sha(document["manifest_sha256"], "manifest_sha256") != manifest_sha256:
        raise ValueError("Owner approval is not bound to this manifest")
    if (
        _sha(document["governance_policy_sha256"], "governance_policy_sha256")
        != policy_sha256
    ):
        raise ValueError("Owner approval is not bound to this governance policy")
    if document["access_probe_id"] != access_probe_id:
        raise ValueError("Owner approval access probe mismatch")
    if document["billing_snapshot_id"] != billing_snapshot_id:
        raise ValueError("Owner approval billing snapshot mismatch")
    if (
        type(document["maximum_calls"]) is not int
        or document["maximum_calls"] != planned_calls
    ):
        raise ValueError("Owner approval call limit must equal planned calls")
    if document["synthetic_or_public_only"] is not True:
        raise ValueError("Owner approval must retain the data-scope restriction")


def _artifact_path(bundle_path: Path, value: Any, name: str) -> Path:
    relative = Path(_text(value, name))
    if relative.is_absolute():
        raise ValueError(f"{name} must be relative to the bundle")
    resolved = (bundle_path.parent / relative).resolve()
    if not resolved.is_relative_to(bundle_path.parent.resolve()):
        raise ValueError(f"{name} must stay inside the bundle directory")
    return resolved


def validate_readiness_bundle(
    bundle_path: Path, *, expected_manifest_path: Path | None = None
) -> dict[str, Any]:
    """Validate a pre-run or post-run bundle and return its preflight report."""

    bundle = json.loads(bundle_path.read_text())
    if not isinstance(bundle, dict):
        raise ValueError("Readiness bundle must be an object")
    _exact(bundle, {"version", "phase", "artifacts"}, "readiness bundle")
    if bundle["version"] != 1 or bundle["phase"] not in {"pre_run", "post_run"}:
        raise ValueError("Readiness bundle version or phase is unsupported")
    artifacts = bundle["artifacts"]
    if not isinstance(artifacts, dict):
        raise ValueError("Bundle artifacts must be an object")
    fields = {
        "governance",
        "curation_manifest",
        "execution_manifest",
        "billing_snapshot",
        "access_probe",
        "owner_approval",
        "run_directory",
        "review_ledger",
        "savings_evidence",
    }
    _exact(artifacts, fields, "bundle artifacts")
    paths = {
        field: _artifact_path(bundle_path, artifacts[field], field)
        for field in fields
        if artifacts[field] is not None
    }
    post_fields = {"run_directory", "review_ledger", "savings_evidence"}
    required_pre_fields = fields - post_fields
    if not required_pre_fields <= paths.keys():
        raise ValueError("Bundle is missing a required pre-run artifact")
    if bundle["phase"] == "pre_run" and any(
        artifacts[field] is not None for field in post_fields
    ):
        raise ValueError("Pre-run bundle cannot contain post-run artifacts")
    if bundle["phase"] == "post_run" and not post_fields <= paths.keys():
        raise ValueError("Post-run bundle requires run, review, and savings artifacts")

    governance, blockers = load_governance(paths["governance"])
    if blockers:
        raise ValueError("Readiness bundle governance is incomplete")
    curation = json.loads(paths["curation_manifest"].read_text())
    validate_curation_manifest(curation)
    manifest, manifest_digest = load_manifest(paths["execution_manifest"])
    if manifest != compile_execution_manifest(curation):
        raise ValueError("Execution manifest differs from compiled curation")
    if (
        expected_manifest_path is not None
        and paths["execution_manifest"] != expected_manifest_path.resolve()
    ):
        raise ValueError("Bundle execution manifest differs from requested manifest")
    readiness = governance["readiness"]
    if readiness["case_manifest_sha256"] != manifest_digest:
        raise ValueError("Governance is not bound to the execution manifest")
    if readiness["curator_id"] != curation["curation"]["curator_id"]:
        raise ValueError("Governance curator differs from curation")

    billing = json.loads(paths["billing_snapshot"].read_text())
    validate_billing_snapshot(billing, readiness["billing_snapshot_id"])
    assignments = {(task["model"], task["effort"]) for task in manifest["tasks"]}
    if {model for model, _ in assignments} - set(billing["model_rates"]):
        raise ValueError("Billing snapshot does not price every manifest model")
    access = json.loads(paths["access_probe"].read_text())
    validate_access_probe(
        access,
        expected_id=readiness["model_access_probe_id"],
        manifest_sha256=manifest_digest,
        required_assignments=assignments,
    )
    approval = json.loads(paths["owner_approval"].read_text())
    validate_owner_approval(
        approval,
        expected_id=readiness["owner_run_approval_id"],
        manifest_sha256=manifest_digest,
        policy_sha256=governance_policy_sha256(governance),
        access_probe_id=readiness["model_access_probe_id"],
        billing_snapshot_id=readiness["billing_snapshot_id"],
        planned_calls=governance["sample"]["planned_calls"],
    )
    approved_at = _time(approval["approved_at"], "approved_at")
    access_at = _time(access["observed_at"], "access observed_at")
    billing_at = _time(billing["captured_at"], "billing captured_at")
    if approved_at < access_at or approved_at < billing_at:
        raise ValueError("Owner approval cannot precede access or billing evidence")

    report: dict[str, Any] = {
        "phase": bundle["phase"],
        "manifest_sha256": manifest_digest,
        "governance_policy_sha256": governance_policy_sha256(governance),
        "governance_sha256": file_sha256(paths["governance"]),
        "pre_run_authorized": True,
        "post_run_evidence_valid": False,
        "external_evidence_claimed_not_proven": True,
    }
    if bundle["phase"] == "post_run":
        run_directory = paths["run_directory"]
        run_file = run_directory / "run.json"
        run = json.loads(run_file.read_text())
        if run.get("manifest_sha256") != manifest_digest:
            raise ValueError("Run is not bound to the execution manifest")
        validate_candidate_measurements(manifest, run_directory)
        review = json.loads(paths["review_ledger"].read_text())
        validate_blinded_review_ledger(
            review,
            manifest,
            manifest_sha256=manifest_digest,
            run_sha256=file_sha256(run_file),
            response_directory=run_directory,
        )
        if review["reviewer_id"] != readiness["reviewer_id"]:
            raise ValueError("Governance reviewer differs from review ledger")
        savings = json.loads(paths["savings_evidence"].read_text())
        validate_savings_evidence(
            savings,
            manifest_sha256=manifest_digest,
            run_sha256=file_sha256(run_file),
            review_ledger_sha256=file_sha256(paths["review_ledger"]),
            billing_snapshot_id=readiness["billing_snapshot_id"],
        )
        if savings["billing_snapshot"] != billing:
            raise ValueError("Savings evidence differs from the bound billing snapshot")
        report["post_run_evidence_valid"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_readiness_bundle(
        args.bundle.resolve(),
        expected_manifest_path=args.manifest,
    )
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered)


if __name__ == "__main__":
    main()
