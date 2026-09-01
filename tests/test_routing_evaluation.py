import json
from dataclasses import asdict
from pathlib import Path

from backend.evaluation.routing import evaluate_corpus

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "tests/fixtures/routing_corpus_v1.json"
BASELINE = ROOT / "docs/evaluations/routing-v1-report.json"


def test_routing_corpus_meets_release_thresholds() -> None:
    report = evaluate_corpus(CORPUS)

    assert report.accepted, report.acceptance_failures
    assert report.metrics.constraint_violation_rate == 0.0
    assert report.metrics.outcome_coverage == 1.0
    assert report.metrics.quality_label_coverage == 0.0
    assert all(scenario.counterfactual_selections for scenario in report.scenarios)


def test_checked_in_routing_report_matches_current_policy() -> None:
    report = evaluate_corpus(CORPUS)
    baseline = json.loads(BASELINE.read_text())

    assert baseline == {
        "accepted": report.accepted,
        "corpus_version": report.corpus_version,
        "metrics": asdict(report.metrics),
        "policy_version": report.policy_version,
    }
