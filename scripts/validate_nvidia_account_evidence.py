"""Validate sanitized NVIDIA account/dashboard evidence for P2B-002."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

APPROVED_MODELS = (
    "moonshotai/kimi-k3",
    "deepseek-ai/deepseek-v4.1-flash",
)
EXPECTED_BASE_URL = "https://integrate.api.nvidia.com/"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AccountRouteEvidence(BaseModel):
    """One exact account-visible route without provider response content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    configured_model: Literal["moonshotai/kimi-k3", "deepseek-ai/deepseek-v4.1-flash"]
    provider_route: Literal["moonshotai/kimi-k3", "deepseek-ai/deepseek-v4.1-flash"]
    account_visible: bool
    entitlement: Literal["free", "paid", "unknown"]
    readiness: Literal["ready", "not_ready", "unknown"]
    recent_request_disposition: Literal[
        "completed", "pending", "rejected", "timed_out", "not_observed", "unknown"
    ]

    @model_validator(mode="after")
    def require_exact_route_mapping(self) -> AccountRouteEvidence:
        if self.provider_route != self.configured_model:
            raise ValueError("provider route must exactly match configured model")
        return self


class NvidiaAccountEvidence(BaseModel):
    """Closed, content-free account evidence required by DEC-007."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    evidence_type: Literal["nvidia_account_route_mapping"]
    source_type: Literal["authenticated_dashboard", "provider_support"]
    provider: Literal["NVIDIA"]
    base_url: HttpUrl
    observed_at: datetime
    account_reference_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    routes: tuple[AccountRouteEvidence, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_identity_contract(self) -> NvidiaAccountEvidence:
        if str(self.base_url) != EXPECTED_BASE_URL:
            raise ValueError("base_url must be the approved NVIDIA hosted API origin")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        if self.account_reference_sha256 == self.evidence_artifact_sha256:
            raise ValueError("account and evidence artifact digests must be distinct")
        configured = tuple(route.configured_model for route in self.routes)
        if len(set(configured)) != len(configured):
            raise ValueError("route entries must be unique")
        if set(configured) != set(APPROVED_MODELS):
            raise ValueError("evidence must cover both exact approved routes")
        return self

    @property
    def mapping_complete(self) -> bool:
        return all(
            route.account_visible
            and route.entitlement == "free"
            and route.readiness == "ready"
            for route in self.routes
        )


def load_account_evidence(path: Path) -> NvidiaAccountEvidence:
    return NvidiaAccountEvidence.model_validate_json(path.read_text(encoding="utf-8"))


def sanitized_summary(evidence: NvidiaAccountEvidence) -> dict[str, object]:
    return {
        "schema_version": evidence.schema_version,
        "evidence_type": evidence.evidence_type,
        "source_type": evidence.source_type,
        "provider": evidence.provider,
        "base_url": str(evidence.base_url),
        "observed_at": evidence.observed_at.isoformat(),
        "mapping_complete": evidence.mapping_complete,
        "routes": [
            {
                "configured_model": route.configured_model,
                "account_visible": route.account_visible,
                "entitlement": route.entitlement,
                "readiness": route.readiness,
                "recent_request_disposition": route.recent_request_disposition,
            }
            for route in evidence.routes
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        evidence = load_account_evidence(_parse_args().evidence)
    except (OSError, ValidationError):
        print("invalid sanitized NVIDIA account evidence", file=sys.stderr)
        return 2
    print(json.dumps(sanitized_summary(evidence), indent=2, sort_keys=True))
    return 0 if evidence.mapping_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
