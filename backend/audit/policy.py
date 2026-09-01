from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.audit.contracts import AuditReport, AuditSeverity


class EvaluationAction(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    REGENERATE = "regenerate"
    VERIFY = "verify"
    REROUTE = "reroute"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    iteration: int
    maximum_iterations: int = 2
    high_risk: bool = False
    independent_verification_complete: bool = False

    def __post_init__(self) -> None:
        if self.iteration < 0 or self.maximum_iterations < 0:
            raise ValueError("Evaluation iteration values cannot be negative.")


@dataclass(frozen=True, slots=True)
class EvaluationDecision:
    policy_version: str
    action: EvaluationAction
    reasons: tuple[str, ...]
    iteration: int


def decide(report: AuditReport, context: EvaluationContext) -> EvaluationDecision:
    reasons: list[str] = []
    if context.iteration >= context.maximum_iterations:
        return EvaluationDecision(
            "ryuk-audit-v1",
            EvaluationAction.ESCALATE,
            ("loop_bound_reached",),
            context.iteration,
        )
    if context.high_risk and not context.independent_verification_complete:
        return EvaluationDecision(
            "ryuk-audit-v1",
            EvaluationAction.VERIFY,
            ("independent_verification_required",),
            context.iteration,
        )
    if report.maximum_severity >= AuditSeverity.CRITICAL:
        reasons.append("critical_finding")
        action = EvaluationAction.REROUTE
    elif report.contradictions:
        reasons.append("contradiction")
        action = EvaluationAction.REGENERATE
    elif report.instruction_failures or report.maximum_severity >= AuditSeverity.ERROR:
        reasons.append("correctable_failure")
        action = EvaluationAction.REVISE
    elif report.uncertainty >= 0.5 or any(
        claim.supported is None for claim in report.claims
    ):
        reasons.append("verification_needed")
        action = EvaluationAction.VERIFY
    else:
        reasons.append("acceptance_rules_satisfied")
        action = EvaluationAction.ACCEPT
    return EvaluationDecision(
        "ryuk-audit-v1", action, tuple(reasons), context.iteration
    )
