from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.evaluation.serving import ServingBenchmark, evaluate_candidate


def _benchmark(value: dict[str, Any]) -> ServingBenchmark:
    return ServingBenchmark(**value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a Dynamo or TensorRT-LLM benchmark against a baseline."
    )
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.report.read_text(encoding="utf-8"))
    decision = evaluate_candidate(
        _benchmark(payload["baseline"]), _benchmark(payload["candidate"])
    )
    print(
        json.dumps({"status": decision.status, "reasons": decision.reasons}, indent=2)
    )
    return 0 if decision.status == "adopt" else 2


if __name__ == "__main__":
    raise SystemExit(main())
