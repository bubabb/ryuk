"""Sequential opt-in Codex CLI pilot; never executes generated code itself."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # Support direct `python scripts/...py` invocation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_allocation_governance import load_governance  # noqa: E402
from scripts.model_allocation_manifest import load_manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "evals/model_allocation/pilot.json"
SCHEMA = ROOT / "evals/model_allocation/response.schema.json"


def authorize_manifest_run(
    manifest: dict[str, Any], manifest_digest: str, governance_path: Path | None
) -> None:
    """Require a ready, hash-bound governance record for v3 and later runs."""
    version = manifest.get("version", 1)
    if type(version) is not int or version < 1:
        raise ValueError("Manifest version must be a positive integer")
    if version < 3:
        return
    if governance_path is None:
        raise ValueError("V3 model calls require a governance record")
    governance, blockers = load_governance(governance_path)
    if blockers:
        raise ValueError("V3 model calls are blocked by incomplete governance")
    if governance["readiness"]["case_manifest_sha256"] != manifest_digest:
        raise ValueError("Governance is not bound to this resolved manifest")


def prompt_for(task: dict[str, Any]) -> str:
    return (
        "You are completing one first-pass development evaluation task. "
        "Use only this prompt. Do not use tools, read files, browse, delegate, "
        "or modify anything. No test answers or feedback will be provided. "
        "Return a JSON object with one string field, content. That string must "
        "contain your requested deliverable, without Markdown fences. "
        "All data is synthetic.\n\nTask:\n" + task["prompt"]
    )


def run_task(
    task: dict[str, Any], directory: Path, *, infrastructure_retry: bool = False
) -> dict[str, Any]:
    target = directory / task["id"]
    target.mkdir(exist_ok=infrastructure_retry)
    prompt = prompt_for(task)
    (target / "prompt.txt").write_text(prompt)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ryuk-model-pilot-") as workspace:
        output = Path(workspace) / "answer.json"
        command = [
            "codex",
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            workspace,
            "-m",
            task["model"],
            "-c",
            f'model_reasoning_effort="{task["effort"]}"',
            "--json",
            "--output-schema",
            str(SCHEMA),
            "-o",
            str(output),
            "-",
        ]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return {
                "id": task["id"],
                "status": "infrastructure_timeout",
                "model_requested": task["model"],
                "effort": task["effort"],
                "usage": None,
                "seconds": time.monotonic() - started,
            }
        events = []
        for line in completed.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        usages = [e.get("usage") for e in events if e.get("type") == "turn.completed"]
        tool_items = [
            e.get("item", {}).get("type")
            for e in events
            if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") not in ("agent_message", "reasoning")
        ]
        result = {
            "id": task["id"],
            "model_requested": task["model"],
            "model_served_verified": False,
            "effort": task["effort"],
            "seconds": time.monotonic() - started,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "returncode": completed.returncode,
            "usage": usages[-1] if usages else None,
            "tool_items": tool_items,
            "status": "completed"
            if completed.returncode == 0
            else "infrastructure_error",
        }
        if output.exists():
            (target / "response.json").write_text(output.read_text())
        # Raw diagnostics stay outside the repository; no auth configuration is read.
        if completed.returncode:
            (target / "error.txt").write_text(
                "CLI execution failed; no model-quality score assigned.\n"
            )
        return result


def prepare_infrastructure_retry(
    measurement_file: Path, policy: dict[str, Any]
) -> None:
    """Archive an eligible failed attempt before its one declared retry."""
    measurement = json.loads(measurement_file.read_text())
    if measurement["status"] not in policy.get("retry_statuses", []):
        raise ValueError(
            "Resume is permitted only for declared infrastructure failures"
        )
    attempts = measurement_file.parent / "infrastructure_attempts"
    attempts.mkdir(exist_ok=True)
    archived = sorted(attempts.glob("*.json"))
    maximum = policy.get("maximum_infrastructure_attempts_per_task", 1)
    if len(archived) + 1 >= maximum:
        raise ValueError(
            f"Infrastructure retry limit reached for {measurement_file.parent.name}"
        )
    (attempts / f"{len(archived) + 1:03d}.json").write_text(
        json.dumps(measurement, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Invoke configured models")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue after recorded infrastructure failures",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=PILOT)
    parser.add_argument("--governance", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest, manifest_digest = load_manifest(manifest_path)
    if not args.run:
        print(
            f"Prepared {len(manifest['tasks'])} tasks; --run required for model calls"
        )
        return
    authorize_manifest_run(manifest, manifest_digest, args.governance)
    args.output.mkdir(parents=True, exist_ok=args.resume)
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "baseline_commit": manifest["baseline_commit"],
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": manifest_digest,
        "cli_version": subprocess.check_output(
            ["codex", "--version"], text=True
        ).strip(),
        "protocol": "single turn per task; no feedback/retry; no tools",
    }
    run_file = args.output / "run.json"
    if args.resume:
        original = json.loads(run_file.read_text())
        if original["manifest_sha256"] != metadata["manifest_sha256"]:
            raise ValueError("Cannot resume with a changed pilot manifest")
    else:
        run_file.write_text(json.dumps(metadata, indent=2) + "\n")
    for task in manifest["tasks"]:
        folder = args.output / task["id"]
        measurement_file = folder / "measurement.json"
        infrastructure_retry = False
        if measurement_file.exists():
            measurement = json.loads(measurement_file.read_text())
            if not args.resume or measurement["status"] == "completed":
                continue
            policy = manifest.get("resume_policy") or {}
            prepare_infrastructure_retry(measurement_file, policy)
            infrastructure_retry = True
        result = run_task(task, args.output, infrastructure_retry=infrastructure_retry)
        (folder / "measurement.json").write_text(json.dumps(result, indent=2) + "\n")
        print(task["id"], task["model"], result["status"], flush=True)
        if result["status"] != "completed":
            print(
                "Stopped on infrastructure failure; remaining tasks unrun.", flush=True
            )
            break


if __name__ == "__main__":
    main()
