import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.validate_nvidia_failure_evidence import (
    NvidiaFailureEvidence,
    load_failure_evidence,
    main,
    sanitized_summary,
)


def _payload(event_type: str = "cancellation_acknowledged") -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_type": "nvidia_failure_behavior",
        "source_type": "provider_support",
        "observed_at": "2026-09-29T10:00:00-04:00",
        "account_reference_sha256": "a" * 64,
        "evidence_artifact_sha256": "b" * 64,
        "observation": {
            "model": "moonshotai/kimi-k3",
            "event_type": event_type,
            "evidence_level": "observed",
            "status_code": 200,
            "provider_acknowledged": True,
            "request_disposition": "cancelled",
            "execution_terminated": "yes",
            "late_result": "not_observed",
            "retry_after_present": False,
        },
    }


def test_valid_observed_cancellation_is_sanitized() -> None:
    evidence = NvidiaFailureEvidence.model_validate(_payload())

    summary = sanitized_summary(evidence)

    assert summary["observed_behavior"] is True
    rendered = json.dumps(summary)
    assert "a" * 64 not in rendered
    assert "b" * 64 not in rendered


@pytest.mark.parametrize(
    ("event_type", "updates", "message"),
    [
        (
            "asynchronous_pending",
            {"status_code": 200, "request_disposition": "pending"},
            "HTTP 202",
        ),
        (
            "cancellation_acknowledged",
            {"provider_acknowledged": False},
            "provider acknowledgment",
        ),
        ("late_result", {"late_result": "unknown"}, "observed result"),
        ("malformed_response", {"evidence_level": "documented_contract"}, "observed"),
        ("overload", {"status_code": 500}, "429 or 503"),
    ],
)
def test_contradictory_event_claims_are_rejected(
    event_type: str, updates: dict[str, object], message: str
) -> None:
    payload = _payload(event_type)
    observation = payload["observation"]
    assert isinstance(observation, dict)
    observation.update(updates)

    with pytest.raises(ValidationError, match=message):
        NvidiaFailureEvidence.model_validate(payload)


def test_documented_contract_cannot_claim_observed_outcome() -> None:
    payload = _payload("asynchronous_pending")
    payload["source_type"] = "official_documentation"
    payload["account_reference_sha256"] = None
    observation = payload["observation"]
    assert isinstance(observation, dict)
    observation.update(
        {
            "evidence_level": "documented_contract",
            "status_code": 202,
            "request_disposition": "pending",
            "provider_acknowledged": False,
            "execution_terminated": "yes",
            "late_result": "unknown",
        }
    )

    with pytest.raises(ValidationError, match="cannot claim"):
        NvidiaFailureEvidence.model_validate(payload)


def test_source_and_evidence_level_must_agree() -> None:
    documentation = _payload()
    documentation["source_type"] = "official_documentation"
    documentation["account_reference_sha256"] = None
    with pytest.raises(ValidationError, match="cannot be marked observed"):
        NvidiaFailureEvidence.model_validate(documentation)

    response = _payload("asynchronous_pending")
    response["source_type"] = "naturally_observed_response"
    observation = response["observation"]
    assert isinstance(observation, dict)
    observation.update(
        {
            "evidence_level": "documented_contract",
            "status_code": 202,
            "request_disposition": "pending",
            "execution_terminated": "unknown",
        }
    )
    with pytest.raises(ValidationError, match="must be marked observed"):
        NvidiaFailureEvidence.model_validate(response)


def test_account_reference_rules_and_distinct_digests() -> None:
    missing = _payload()
    missing["account_reference_sha256"] = None
    with pytest.raises(ValidationError, match="account-specific"):
        NvidiaFailureEvidence.model_validate(missing)

    reused = _payload()
    reused["evidence_artifact_sha256"] = "a" * 64
    with pytest.raises(ValidationError, match="digests must be distinct"):
        NvidiaFailureEvidence.model_validate(reused)


def test_unknown_fields_and_raw_references_are_rejected() -> None:
    extra = _payload()
    extra["response_body"] = "secret provider detail"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NvidiaFailureEvidence.model_validate(extra)

    raw = _payload()
    raw["account_reference_sha256"] = "account@example.com"
    with pytest.raises(ValidationError):
        NvidiaFailureEvidence.model_validate(raw)


def test_naive_timestamp_is_rejected() -> None:
    payload = _payload()
    payload["observed_at"] = "2026-09-29T10:00:00"

    with pytest.raises(ValidationError, match="timezone"):
        NvidiaFailureEvidence.model_validate(payload)


def test_loader_uses_closed_contract(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    evidence = load_failure_evidence(path)

    assert evidence.observed_behavior is True


def test_cli_does_not_echo_rejected_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _payload()
    payload["response_body"] = "must-not-appear"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validator", str(path)])

    assert main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid sanitized NVIDIA failure evidence\n"
    assert "must-not-appear" not in captured.err
