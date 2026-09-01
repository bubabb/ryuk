from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backend.audit.contracts import AuditIdentity, AuditReport
from backend.audit.deterministic import ValidationPolicy, validate_output
from backend.audit.policy import EvaluationAction, EvaluationContext, decide


@dataclass(frozen=True, slots=True)
class AuditEvaluationReport:
    corpus_version: str
    count: int
    action_accuracy: float
    false_accept_rate: float
    accepted: bool


def evaluate_audit_corpus(path: Path) -> AuditEvaluationReport:
    corpus = json.loads(path.read_text(encoding="utf-8"))
    correct = 0
    false_accepts = 0
    for item in corpus["cases"]:
        findings = validate_output(item["output"], ValidationPolicy(**item["policy"]))
        report = AuditReport(
            "ryuk-audit-report-v1",
            AuditIdentity("fixture-generator", "fixture-model", "v1"),
            None,
            findings,
        )
        action = decide(report, EvaluationContext(iteration=0)).action
        expected = EvaluationAction(item["expected_action"])
        correct += action is expected
        false_accepts += (
            action is EvaluationAction.ACCEPT
            and expected is not EvaluationAction.ACCEPT
        )
    count = len(corpus["cases"])
    accuracy = correct / count
    false_accept_rate = false_accepts / count
    thresholds = corpus["thresholds"]
    return AuditEvaluationReport(
        corpus["corpus_version"],
        count,
        accuracy,
        false_accept_rate,
        accuracy >= thresholds["minimum_action_accuracy"]
        and false_accept_rate <= thresholds["maximum_false_accept_rate"],
    )
