from pathlib import Path

from backend.audit.contracts import (
    AuditIdentity,
    AuditReport,
    AuditSeverity,
    ClaimAssessment,
)
from backend.audit.deterministic import ValidationPolicy, validate_output
from backend.audit.policy import EvaluationAction, EvaluationContext, decide
from backend.evaluation.audit import evaluate_audit_corpus
from backend.inference.advanced import JSONSchemaConstraint

FIXTURE = Path(__file__).parent / "fixtures" / "audit_corpus_v1.json"


def identity(name: str) -> AuditIdentity:
    return AuditIdentity(name, f"{name}-model", "revision-1")


def test_deterministic_checks_cover_required_validation_classes() -> None:
    policy = ValidationPolicy(
        required_sections=("Summary",),
        require_citations=True,
        minimum_chars=20,
        maximum_chars=100,
        language="ascii",
        forbidden_phrases=("bypass policy",),
    )
    findings = validate_output("bypass policy sk-abcdefghijklmnop", policy)
    codes = {item.code for item in findings}
    assert "missing_section:Summary" in codes
    assert "citation_missing" in codes
    assert "forbidden_phrase" in codes
    assert "possible_secret_leak" in codes


def test_schema_check_is_deterministic() -> None:
    schema = JSONSchemaConstraint(
        {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        }
    )
    findings = validate_output('{"answer": 4}', ValidationPolicy(output_schema=schema))
    assert findings[0].code == "answer:wrong_type"


def test_evaluation_policy_is_bounded_and_requires_independent_verification() -> None:
    report = AuditReport("v1", identity("generator"), identity("auditor"), ())
    high_risk = decide(report, EvaluationContext(0, high_risk=True))
    assert high_risk.action is EvaluationAction.VERIFY
    bounded = decide(report, EvaluationContext(2, maximum_iterations=2))
    assert bounded.action is EvaluationAction.ESCALATE


def test_uncertain_model_audit_is_not_accepted() -> None:
    report = AuditReport(
        "v1",
        identity("generator"),
        identity("auditor"),
        (),
        claims=(ClaimAssessment("The claim", True, None, 0.8),),
        uncertainty=0.8,
    )
    decision = decide(report, EvaluationContext(0))
    assert decision.action is EvaluationAction.VERIFY


def test_critical_deterministic_finding_reroutes() -> None:
    findings = validate_output("sk-abcdefghijklmnop", ValidationPolicy())
    report = AuditReport("v1", identity("generator"), None, findings)
    assert report.maximum_severity is AuditSeverity.CRITICAL
    assert decide(report, EvaluationContext(0)).action is EvaluationAction.REROUTE


def test_labeled_audit_corpus_passes_gate() -> None:
    report = evaluate_audit_corpus(FIXTURE)
    assert report.accepted
    assert report.action_accuracy == 1.0
    assert report.false_accept_rate == 0.0
