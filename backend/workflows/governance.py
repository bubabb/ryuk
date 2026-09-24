"""Server-owned workflow acceptance and budget configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.audit.deterministic import ValidationPolicy
from backend.workflows.validation import policy_snapshot


class AcceptanceRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    required_sections: list[str] = Field(default_factory=list, max_length=32)
    forbidden_phrases: list[str] = Field(default_factory=list, max_length=32)
    require_citations: bool = False
    minimum_chars: int = Field(default=1, ge=0)
    maximum_chars: int = Field(default=100_000, ge=1, le=100_000)
    language: Literal["ascii"] | None = None

    def policy(self) -> ValidationPolicy:
        return ValidationPolicy(
            required_sections=tuple(self.required_sections),
            forbidden_phrases=tuple(self.forbidden_phrases),
            require_citations=self.require_citations,
            minimum_chars=self.minimum_chars,
            maximum_chars=self.maximum_chars,
            language=self.language,
        )

    @model_validator(mode="after")
    def supported(self) -> AcceptanceRules:
        policy_snapshot(self.policy())
        return self


class WorkflowLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    deadline_seconds: float = Field(gt=0, le=3600, allow_inf_nan=False)
    max_attempts: int = Field(ge=1, le=10)
    max_output_tokens: int = Field(ge=1, le=32768)


class WorkflowPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: str = Field(min_length=1, max_length=128)
    acceptance: AcceptanceRules
    budget: WorkflowLimits

    def binding(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "policy": policy_snapshot(self.acceptance.policy()),
            "budget": self.budget.model_dump(),
        }


def load_workflow_policies(path: Path | None) -> dict[str, WorkflowPolicy]:
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or any(
        not isinstance(tenant, str) or not tenant.strip() for tenant in document
    ):
        raise ValueError("Workflow policy configuration must map tenants to policies")
    return {
        tenant: WorkflowPolicy.model_validate(policy)
        for tenant, policy in document.items()
    }
