"""Load immutable model-allocation manifests and their explicit overlays."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    """Return a resolved manifest and a hash covering every source file."""
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    if "base_manifest" not in raw:
        # Preserve compatibility with already-recorded v1 runs.
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
            key: value
            for key, value in override.items()
            if key != "checks_append"
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
    return resolved, hashlib.sha256(digest_payload).hexdigest()
