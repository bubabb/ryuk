import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.evaluation.audit import evaluate_audit_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Ryuk audit policy.")
    parser.add_argument(
        "corpus",
        type=Path,
        nargs="?",
        default=Path("tests/fixtures/audit_corpus_v1.json"),
    )
    args = parser.parse_args()
    report = evaluate_audit_corpus(args.corpus)
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
