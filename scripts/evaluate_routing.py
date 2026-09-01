import argparse
import json
from pathlib import Path

from backend.evaluation.routing import evaluate_corpus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/routing_corpus_v1.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_corpus(args.corpus)
    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered)
    if not report.accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
