from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.audit.contracts import AuditFinding, AuditSeverity, FindingKind
from backend.inference.advanced import JSONSchemaConstraint, validate_json_schema

_CITATION = re.compile(r"\[[^\]\n]+\]\(https://[^)\s]+\)")
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|nvapi)-[A-Za-z0-9_-]{16,}\b"),
)


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    required_sections: tuple[str, ...] = ()
    require_citations: bool = False
    minimum_chars: int = 0
    maximum_chars: int = 100_000
    language: str | None = None
    forbidden_phrases: tuple[str, ...] = ()
    output_schema: JSONSchemaConstraint | None = None

    def __post_init__(self) -> None:
        if self.minimum_chars < 0 or self.maximum_chars < self.minimum_chars:
            raise ValueError("Invalid validation length bounds.")


def validate_output(text: str, policy: ValidationPolicy) -> tuple[AuditFinding, ...]:
    findings: list[AuditFinding] = []
    if not policy.minimum_chars <= len(text) <= policy.maximum_chars:
        findings.append(
            _finding(FindingKind.LENGTH, AuditSeverity.ERROR, "length_out_of_bounds")
        )
    for section in policy.required_sections:
        if section.casefold() not in text.casefold():
            findings.append(
                _finding(
                    FindingKind.REQUIRED_SECTION,
                    AuditSeverity.ERROR,
                    f"missing_section:{section}",
                )
            )
    if policy.require_citations and _CITATION.search(text) is None:
        findings.append(
            _finding(FindingKind.CITATION, AuditSeverity.ERROR, "citation_missing")
        )
    if policy.language == "ascii" and not text.isascii():
        findings.append(
            _finding(FindingKind.LANGUAGE, AuditSeverity.WARNING, "language_mismatch")
        )
    for phrase in policy.forbidden_phrases:
        if phrase.casefold() in text.casefold():
            findings.append(
                _finding(FindingKind.POLICY, AuditSeverity.CRITICAL, "forbidden_phrase")
            )
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        findings.append(
            _finding(FindingKind.SECRET, AuditSeverity.CRITICAL, "possible_secret_leak")
        )
    if policy.output_schema is not None:
        errors: tuple[str, ...]
        try:
            value: Any = json.loads(text)
        except json.JSONDecodeError:
            errors = ("root:invalid_json",)
        else:
            errors = validate_json_schema(value, policy.output_schema)
        findings.extend(
            _finding(FindingKind.SCHEMA, AuditSeverity.ERROR, error) for error in errors
        )
    return tuple(findings)


def _finding(kind: FindingKind, severity: AuditSeverity, code: str) -> AuditFinding:
    return AuditFinding(
        kind, severity, code, "Output failed a deterministic validation rule."
    )
