import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_controller_backend_has_no_vllm_dependency() -> None:
    violations: list[str] = []
    for path in (ROOT / "backend").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "vllm" or name.startswith("vllm.") for name in names):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_gpu_spike_cli_is_inspectable_without_vllm_installed() -> None:
    result = subprocess.run(
        [sys.executable, "spikes/vllm/async_llm_spike.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--tensor-parallel-size" in result.stdout


def test_checked_in_result_is_explicitly_not_a_gpu_benchmark() -> None:
    result = json.loads(
        (ROOT / "spikes/vllm/results/mac-controller-preflight.json").read_text()
    )
    assert result["vllm_installed"] is False
    assert result["nvidia_smi"] is None
    assert "not an inference benchmark" in result["note"]
