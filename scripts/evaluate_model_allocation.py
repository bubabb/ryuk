"""Sequential opt-in Codex CLI pilot; never executes generated code itself."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "evals/model_allocation/pilot.json"
SCHEMA = ROOT / "evals/model_allocation/response.schema.json"


def prompt_for(task: dict[str, Any]) -> str:
    return (
        "You are completing one first-pass development evaluation task. "
        "Use only this prompt. Do not use tools, read files, browse, delegate, "
        "or modify anything. No test answers or feedback will be provided. "
        "Return a JSON object with one string field, content. That string must "
        "contain your requested deliverable, without Markdown fences. "
        "All data is synthetic.\n\nTask:\n" + task["prompt"]
    )


def run_task(task: dict[str, Any], directory: Path) -> dict[str, Any]:
    target = directory / task["id"]
    target.mkdir()  # Never silently overwrite a first-pass attempt.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Invoke configured models")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue after recorded infrastructure failures",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(PILOT.read_text())
    if not args.run:
        print(
            f"Prepared {len(manifest['tasks'])} tasks; --run required for model calls"
        )
        return
    args.output.mkdir(parents=True, exist_ok=args.resume)
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "baseline_commit": manifest["baseline_commit"],
        "manifest_sha256": hashlib.sha256(PILOT.read_bytes()).hexdigest(),
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
        if (folder / "measurement.json").exists():
            continue
        result = run_task(task, args.output)
        (folder / "measurement.json").write_text(json.dumps(result, indent=2) + "\n")
        print(task["id"], task["model"], result["status"], flush=True)
        if result["status"] != "completed":
            print(
                "Stopped on infrastructure failure; remaining tasks unrun.", flush=True
            )
            break


if __name__ == "__main__":
    main()
