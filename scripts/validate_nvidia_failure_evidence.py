"""Validate sanitized provider failure evidence for P2B-004."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class FailureObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    model: Literal["moonshotai/kimi-k3", "deepseek-ai/deepseek-v4.1-flash"]
    event_type: Literal[
        "asynchronous_pending",
        "cancellation_acknowledged",
        "late_result",
        "malformed_response",
        "overload",
    ]
    evidence_level: Literal["documented_contract", "observed"]
    status_code: Literal[200, 202, 422, 429, 500, 503] | None
    provider_acknowledged: bool
    request_disposition: Literal[
        "completed", "pending", "rejected", "cancelled", "unknown"
    ]
    execution_terminated: Literal["yes", "no", "unknown"]
    late_result: Literal["observed", "not_observed", "unknown"]
    retry_after_present: bool

    @model_validator(mode="after")
    def validate_event_semantics(self) -> FailureObservation:
        if self.event_type == "asynchronous_pending":
            if self.status_code != 202 or self.request_disposition != "pending":
                raise ValueError(
                    "asynchronous pending evidence requires HTTP 202/pending"
                )
        elif self.event_type == "cancellation_acknowledged":
            if not self.provider_acknowledged:
                raise ValueError(
                    "cancellation evidence requires provider acknowledgment"
                )
            if self.request_disposition != "cancelled":
                raise ValueError("acknowledged cancellation must be cancelled")
        elif self.event_type == "late_result":
            if self.late_result != "observed":
                raise ValueError("late-result evidence must record an observed result")
        elif self.event_type == "malformed_response":
            if self.evidence_level != "observed":
                raise ValueError("malformed response must be directly observed")
        elif self.event_type == "overload" and self.status_code not in (429, 503):
            raise ValueError("overload evidence requires HTTP 429 or 503")
        if self.evidence_level == "documented_contract" and any(
            (
                self.execution_terminated != "unknown",
                self.late_result == "observed",
            )
        ):
            raise ValueError("documentation cannot claim an observed provider outcome")
        return self


class NvidiaFailureEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    evidence_type: Literal["nvidia_failure_behavior"]
    source_type: Literal[
        "authenticated_dashboard",
        "provider_support",
        "naturally_observed_response",
        "official_documentation",
    ]
    observed_at: datetime
    account_reference_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    evidence_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    observation: FailureObservation

    @model_validator(mode="after")
    def validate_source_contract(self) -> NvidiaFailureEvidence:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        account_specific = self.source_type != "official_documentation"
        if account_specific != (self.account_reference_sha256 is not None):
            raise ValueError(
                "account-specific evidence requires exactly one account reference"
            )
        if self.source_type == "official_documentation" and (
            self.observation.evidence_level != "documented_contract"
        ):
            raise ValueError("official documentation cannot be marked observed")
        if self.source_type == "naturally_observed_response" and (
            self.observation.evidence_level != "observed"
        ):
            raise ValueError("a naturally observed response must be marked observed")
        if self.account_reference_sha256 == self.evidence_artifact_sha256:
            raise ValueError("account and evidence artifact digests must be distinct")
        return self

    @property
    def observed_behavior(self) -> bool:
        return self.observation.evidence_level == "observed"


def load_failure_evidence(path: Path) -> NvidiaFailureEvidence:
    return NvidiaFailureEvidence.model_validate_json(path.read_text(encoding="utf-8"))


def sanitized_summary(evidence: NvidiaFailureEvidence) -> dict[str, object]:
    observation = evidence.observation
    return {
        "schema_version": evidence.schema_version,
        "evidence_type": evidence.evidence_type,
        "source_type": evidence.source_type,
        "observed_at": evidence.observed_at.isoformat(),
        "observed_behavior": evidence.observed_behavior,
        "observation": {
            "model": observation.model,
            "event_type": observation.event_type,
            "evidence_level": observation.evidence_level,
            "status_code": observation.status_code,
            "provider_acknowledged": observation.provider_acknowledged,
            "request_disposition": observation.request_disposition,
            "execution_terminated": observation.execution_terminated,
            "late_result": observation.late_result,
            "retry_after_present": observation.retry_after_present,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        evidence = load_failure_evidence(_parse_args().evidence)
    except (OSError, ValidationError):
        print("invalid sanitized NVIDIA failure evidence", file=sys.stderr)
        return 2
    print(json.dumps(sanitized_summary(evidence), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
