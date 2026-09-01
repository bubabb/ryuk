from __future__ import annotations

from typing import Any

from backend.inference.engines.managed_http import ManagedHTTPInferenceEngine


class DynamoEngine(ManagedHTTPInferenceEngine):
    """Ryuk adapter for one Dynamo deployment, never an individual worker.

    Ryuk selects this deployment. Dynamo's frontend/router exclusively owns
    worker selection, KV-aware routing, and prefill/decode placement.
    """

    name = "dynamo"
    readiness_path = "/health"

    def __init__(self, *args: Any, topology: str, runtime_version: str, **kwargs: Any):
        if topology not in {"aggregated", "disaggregated"}:
            raise ValueError("Dynamo topology must be aggregated or disaggregated.")
        if not runtime_version.strip():
            raise ValueError("Dynamo runtime version must be pinned.")
        self.topology = topology
        self.runtime_version = runtime_version
        super().__init__(*args, **kwargs)

    def _response_metadata(self, result: dict[str, Any]) -> dict[str, Any]:
        metadata = super()._response_metadata(result)
        metadata.update(
            {"runtime_version": self.runtime_version, "topology": self.topology}
        )
        return metadata
