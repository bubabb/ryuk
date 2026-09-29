import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.validate_phase2b_live_test_manifest import (
    Phase2BLiveTestManifest,
    load_live_test_manifest,
    main,
    sanitized_summary,
)


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "manifest_type": "phase2b_bounded_live_diagnostic",
        "created_at": "2026-09-29T08:00:00-04:00",
        "expires_at": "2026-09-30T08:00:00-04:00",
        "repository_revision": "1" * 40,
        "input_classification": "synthetic_public",
        "paid_spend_usd_max": 0,
        "max_attempts": 1,
        "concurrency": 1,
        "automatic_retry": False,
        "automatic_fallback": False,
        "account_evidence_sha256": "a" * 64,
        "diagnostic_hypothesis_sha256": "b" * 64,
        "owner_approval_sha256": "c" * 64,
        "request": {
            "model": "moonshotai/kimi-k3",
            "purpose": "ordinary_generation_diagnostic",
            "prompt_sha256": "d" * 64,
            "timeout_seconds": 300,
            "max_tokens": 256,
            "temperature": 1,
            "reasoning_effort": "low",
            "stream": False,
        },
        "stop_conditions": {
            "payment_or_subscription": True,
            "entitlement_not_free": True,
            "identity_mismatch": True,
            "unknown_provider_outcome": True,
            "private_or_customer_data": True,
        },
    }


def test_valid_current_manifest_has_sanitized_summary() -> None:
    manifest = Phase2BLiveTestManifest.model_validate(_valid_payload())
    now = datetime.fromisoformat("2026-09-29T12:00:00-04:00")

    summary = sanitized_summary(manifest, now=now)

    assert summary["current"] is True
    rendered = json.dumps(summary)
    for marker in ("a" * 64, "b" * 64, "c" * 64, "d" * 64):
        assert marker not in rendered


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("paid_spend_usd_max", 1),
        ("max_attempts", 2),
        ("concurrency", 2),
        ("automatic_retry", True),
        ("automatic_fallback", True),
        ("input_classification", "private"),
        ("max_attempts", True),
        ("paid_spend_usd_max", False),
    ],
)
def test_unsafe_top_level_settings_are_rejected(field: str, value: object) -> None:
    payload = _valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        Phase2BLiveTestManifest.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_seconds", 301),
        ("max_tokens", 257),
        ("temperature", 1.1),
        ("stream", True),
        ("timeout_seconds", "300"),
    ],
)
def test_unsafe_request_bounds_are_rejected(field: str, value: object) -> None:
    payload = _valid_payload()
    request = payload["request"]
    assert isinstance(request, dict)
    request[field] = value

    with pytest.raises(ValidationError):
        Phase2BLiveTestManifest.model_validate(payload)


def test_false_stop_condition_and_extra_field_are_rejected() -> None:
    disabled_stop = _valid_payload()
    stops = disabled_stop["stop_conditions"]
    assert isinstance(stops, dict)
    stops["identity_mismatch"] = False
    with pytest.raises(ValidationError):
        Phase2BLiveTestManifest.model_validate(disabled_stop)

    extra = _valid_payload()
    extra["authorization"] = "Bearer secret"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Phase2BLiveTestManifest.model_validate(extra)


@pytest.mark.parametrize(
    ("created_at", "expires_at"),
    [
        ("2026-09-29T08:00:00", "2026-09-30T08:00:00-04:00"),
        ("2026-09-29T08:00:00-04:00", "2026-09-29T08:00:00-04:00"),
        ("2026-09-29T08:00:00-04:00", "2026-09-30T08:00:01-04:00"),
    ],
)
def test_invalid_validity_windows_are_rejected(
    created_at: str, expires_at: str
) -> None:
    payload = _valid_payload()
    payload["created_at"] = created_at
    payload["expires_at"] = expires_at

    with pytest.raises(ValidationError):
        Phase2BLiveTestManifest.model_validate(payload)


def test_expired_manifest_fails_closed() -> None:
    manifest = Phase2BLiveTestManifest.model_validate(_valid_payload())
    now = datetime.fromisoformat("2026-09-30T08:00:01-04:00")

    assert manifest.is_current(now=now) is False


def test_digest_reuse_is_rejected() -> None:
    payload = _valid_payload()
    payload["owner_approval_sha256"] = "a" * 64

    with pytest.raises(ValidationError, match="digests must be distinct"):
        Phase2BLiveTestManifest.model_validate(payload)


def test_loader_uses_closed_contract(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    manifest = load_live_test_manifest(path)

    assert manifest.max_attempts == 1


def test_cli_does_not_echo_rejected_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _valid_payload()
    payload["authorization"] = "Bearer must-not-appear"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["validator", str(path), "--expected-revision", "1" * 40]
    )

    assert main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid Phase 2B live-test manifest\n"
    assert "must-not-appear" not in captured.err


def test_cli_rejects_revision_mismatch_without_printing_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["validator", str(path), "--expected-revision", "2" * 40]
    )

    assert main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "live-test manifest revision mismatch\n"
