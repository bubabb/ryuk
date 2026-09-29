"""Validate a fail-closed manifest for one bounded Phase 2B live diagnostic."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40}$"


class LiveRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    model: Literal["moonshotai/kimi-k3", "deepseek-ai/deepseek-v4.1-flash"]
    purpose: Literal["ordinary_generation_diagnostic"]
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    timeout_seconds: float = Field(gt=0, le=300)
    max_tokens: int = Field(gt=0, le=256)
    temperature: float = Field(ge=0, le=1)
    reasoning_effort: Literal["low", "high", "max"] | None = None
    stream: Literal[False]


class StopConditions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    payment_or_subscription: Literal[True]
    entitlement_not_free: Literal[True]
    identity_mismatch: Literal[True]
    unknown_provider_outcome: Literal[True]
    private_or_customer_data: Literal[True]


class Phase2BLiveTestManifest(BaseModel):
    """One short-lived diagnostic preregistration packet, not provider evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    manifest_type: Literal["phase2b_bounded_live_diagnostic"]
    created_at: datetime
    expires_at: datetime
    repository_revision: str = Field(pattern=GIT_SHA_PATTERN)
    input_classification: Literal["synthetic_public"]
    paid_spend_usd_max: Literal[0]
    max_attempts: Literal[1]
    concurrency: Literal[1]
    automatic_retry: Literal[False]
    automatic_fallback: Literal[False]
    account_evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnostic_hypothesis_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    request: LiveRequest
    stop_conditions: StopConditions

    @field_validator("paid_spend_usd_max", "max_attempts", "concurrency", mode="before")
    @classmethod
    def reject_non_integer_bounds(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("integer safety bounds require exact integer values")
        return value

    @field_validator("automatic_retry", "automatic_fallback", mode="before")
    @classmethod
    def reject_non_boolean_controls(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("automatic controls require exact boolean values")
        return value

    @model_validator(mode="after")
    def validate_window_and_references(self) -> Phase2BLiveTestManifest:
        timestamps = (self.created_at, self.expires_at)
        if any(
            value.tzinfo is None or value.utcoffset() is None for value in timestamps
        ):
            raise ValueError("manifest timestamps must include timezone offsets")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.expires_at - self.created_at > timedelta(hours=24):
            raise ValueError("manifest validity cannot exceed 24 hours")
        references = {
            self.account_evidence_sha256,
            self.diagnostic_hypothesis_sha256,
            self.owner_approval_sha256,
            self.request.prompt_sha256,
        }
        if len(references) != 4:
            raise ValueError("manifest evidence and prompt digests must be distinct")
        return self

    def is_current(self, *, now: datetime | None = None) -> bool:
        observed = now or datetime.now(UTC)
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("current time must include a timezone offset")
        return self.created_at <= observed <= self.expires_at


def load_live_test_manifest(path: Path) -> Phase2BLiveTestManifest:
    return Phase2BLiveTestManifest.model_validate_json(path.read_text(encoding="utf-8"))


def sanitized_summary(
    manifest: Phase2BLiveTestManifest, *, now: datetime | None = None
) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "manifest_type": manifest.manifest_type,
        "created_at": manifest.created_at.isoformat(),
        "expires_at": manifest.expires_at.isoformat(),
        "repository_revision": manifest.repository_revision,
        "input_classification": manifest.input_classification,
        "paid_spend_usd_max": manifest.paid_spend_usd_max,
        "max_attempts": manifest.max_attempts,
        "concurrency": manifest.concurrency,
        "automatic_retry": manifest.automatic_retry,
        "automatic_fallback": manifest.automatic_fallback,
        "current": manifest.is_current(now=now),
        "request": {
            "model": manifest.request.model,
            "purpose": manifest.request.purpose,
            "timeout_seconds": manifest.request.timeout_seconds,
            "max_tokens": manifest.request.max_tokens,
            "temperature": manifest.request.temperature,
            "reasoning_effort": manifest.request.reasoning_effort,
            "stream": manifest.request.stream,
        },
        "stop_conditions": manifest.stop_conditions.model_dump(),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        manifest = load_live_test_manifest(args.manifest)
    except (OSError, ValidationError):
        print("invalid Phase 2B live-test manifest", file=sys.stderr)
        return 2
    if (
        re.fullmatch(GIT_SHA_PATTERN, args.expected_revision) is None
        or manifest.repository_revision != args.expected_revision
    ):
        print("live-test manifest revision mismatch", file=sys.stderr)
        return 2
    summary = sanitized_summary(manifest)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["current"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
