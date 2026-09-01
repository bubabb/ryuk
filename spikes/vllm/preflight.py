import importlib.util
import json
import platform
import shutil


def main() -> None:
    result = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "nvidia_smi": shutil.which("nvidia-smi"),
        "vllm_installed": importlib.util.find_spec("vllm") is not None,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
