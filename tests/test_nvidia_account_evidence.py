import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.validate_nvidia_account_evidence import (
    NvidiaAccountEvidence,
    load_account_evidence,
    main,
    sanitized_summary,
)


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_type": "nvidia_account_route_mapping",
        "source_type": "authenticated_dashboard",
        "provider": "NVIDIA",
        "base_url": "https://integrate.api.nvidia.com",
        "observed_at": "2026-09-29T01:00:00-04:00",
        "account_reference_sha256": "a" * 64,
        "evidence_artifact_sha256": "b" * 64,
        "routes": [
            {
                "configured_model": "moonshotai/kimi-k3",
                "provider_route": "moonshotai/kimi-k3",
                "account_visible": True,
                "entitlement": "free",
                "readiness": "ready",
                "recent_request_disposition": "timed_out",
            },
            {
                "configured_model": "deepseek-ai/deepseek-v4.1-flash",
                "provider_route": "deepseek-ai/deepseek-v4.1-flash",
                "account_visible": True,
                "entitlement": "free",
                "readiness": "ready",
                "recent_request_disposition": "completed",
            },
        ],
    }


def test_valid_account_evidence_passes_without_exposing_hashes() -> None:
    evidence = NvidiaAccountEvidence.model_validate(_valid_payload())

    assert evidence.mapping_complete is True
    summary = sanitized_summary(evidence)
    rendered = json.dumps(summary)
    assert summary["mapping_complete"] is True
    assert "a" * 64 not in rendered
    assert "b" * 64 not in rendered


def test_unknown_readiness_fails_closed() -> None:
    payload = _valid_payload()
    routes = payload["routes"]
    assert isinstance(routes, list)
    routes[0]["readiness"] = "unknown"

    evidence = NvidiaAccountEvidence.model_validate(payload)

    assert evidence.mapping_complete is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_reference_sha256", "account@example.com"),
        ("evidence_artifact_sha256", "not-a-digest"),
    ],
)
def test_raw_or_invalid_references_are_rejected(field: str, value: str) -> None:
    payload = _valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        NvidiaAccountEvidence.model_validate(payload)


def test_extra_fields_cannot_hide_secrets_or_support_text() -> None:
    payload = _valid_payload()
    payload["authorization"] = "Bearer secret"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NvidiaAccountEvidence.model_validate(payload)


def test_mismatched_or_duplicate_routes_are_rejected() -> None:
    mismatched = _valid_payload()
    routes = mismatched["routes"]
    assert isinstance(routes, list)
    routes[0]["provider_route"] = "deepseek-ai/deepseek-v4.1-flash"
    with pytest.raises(ValidationError, match="exactly match"):
        NvidiaAccountEvidence.model_validate(mismatched)

    duplicated = _valid_payload()
    duplicate_routes = duplicated["routes"]
    assert isinstance(duplicate_routes, list)
    duplicate_routes[1] = duplicate_routes[0].copy()
    with pytest.raises(ValidationError, match="unique"):
        NvidiaAccountEvidence.model_validate(duplicated)


def test_wrong_origin_and_naive_timestamp_are_rejected() -> None:
    wrong_origin = _valid_payload()
    wrong_origin["base_url"] = "https://example.com"
    with pytest.raises(ValidationError, match="approved NVIDIA"):
        NvidiaAccountEvidence.model_validate(wrong_origin)

    naive_time = _valid_payload()
    naive_time["observed_at"] = "2026-09-29T01:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        NvidiaAccountEvidence.model_validate(naive_time)


def test_account_and_artifact_digests_must_be_distinct() -> None:
    payload = _valid_payload()
    payload["evidence_artifact_sha256"] = "a" * 64

    with pytest.raises(ValidationError, match="digests must be distinct"):
        NvidiaAccountEvidence.model_validate(payload)


def test_file_loader_uses_the_same_closed_contract(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    evidence = load_account_evidence(path)

    assert evidence.mapping_complete is True


def test_cli_does_not_echo_rejected_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _valid_payload()
    payload["authorization"] = "Bearer must-not-appear"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validator", str(path)])

    assert main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid sanitized NVIDIA account evidence\n"
    assert "must-not-appear" not in captured.err
