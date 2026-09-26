"""Load immutable model-allocation manifests and their explicit overlays."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate optional matched-arm contracts without changing v1/v2."""
    comparison = manifest.get("comparison")
    if comparison is None:
        return
    if not isinstance(comparison, dict):
        raise ValueError("Comparison configuration must be an object")
    arms = comparison.get("arms")
    if (
        not isinstance(arms, list)
        or len(arms) < 2
        or any(not isinstance(arm, str) or not arm.strip() for arm in arms)
    ):
        raise ValueError("Comparison arms must be unique nonblank strings")
    if len(set(arms)) != len(arms):
        raise ValueError("Comparison arms must be unique nonblank strings")
    if comparison.get("require_complete_pairs") is not True:
        raise ValueError("Matched comparison must require complete pairs")
    baseline = comparison.get("baseline_arm")
    if baseline not in arms:
        raise ValueError("Comparison baseline_arm must name a declared arm")
    grouped: dict[str, list[dict[str, Any]]] = {}
    task_ids: set[str] = set()
    for task in manifest["tasks"]:
        case_id, arm = task.get("case_id"), task.get("arm")
        if not isinstance(case_id, str) or not case_id.strip() or arm not in arms:
            raise ValueError("Every comparison task needs a valid case_id and arm")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip() or task_id in task_ids:
            raise ValueError("Comparison task IDs must be unique nonblank strings")
        task_ids.add(task_id)
        grouped.setdefault(case_id, []).append(task)
    for case_id, tasks in grouped.items():
        if {task["arm"] for task in tasks} != set(arms) or len(tasks) != len(arms):
            raise ValueError(f"Case {case_id} must occur exactly once in every arm")
        reference = tasks[0]
        for task in tasks[1:]:
            for field in ("prompt", "expected", "checks", "critical", "category"):
                if task.get(field) != reference.get(field):
                    raise ValueError(
                        f"Case {case_id} differs across arms for field {field}"
                    )


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    """Return a resolved manifest and a hash covering every source file."""
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    if "base_manifest" not in raw:
        # Preserve compatibility with already-recorded v1 runs.
        validate_manifest(raw)
        return raw, hashlib.sha256(raw_bytes).hexdigest()
    base_path = path.parent / raw["base_manifest"]
    base, base_digest = load_manifest(base_path)
    resolved = copy.deepcopy(base)
    for key in ("version", "baseline_commit", "purpose", "threshold"):
        if key in raw:
            resolved[key] = raw[key]
    resolved["resume_policy"] = raw.get("resume_policy")
    by_id = {task["id"]: task for task in resolved["tasks"]}
    for task_id, override in raw.get("task_overrides", {}).items():
        if task_id not in by_id:
            raise ValueError(f"Unknown task override: {task_id}")
        append = override.get("checks_append", [])
        replacements = {
            key: value for key, value in override.items() if key != "checks_append"
        }
        by_id[task_id].update(replacements)
        if append:
            by_id[task_id]["checks"] = [*by_id[task_id]["checks"], *append]
    digest_payload = json.dumps(
        {
            "resolved": resolved,
            "sources": {
                path.name: hashlib.sha256(raw_bytes).hexdigest(),
                base_path.name: base_digest,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    validate_manifest(resolved)
    return resolved, hashlib.sha256(digest_payload).hexdigest()
