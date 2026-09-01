from __future__ import annotations

from typing import Any

from backend.inference.deployment import IdentityDiscovery
from backend.inference.engines.managed_http import ManagedHTTPInferenceEngine
from backend.inference.errors import UpstreamProtocolFailure


class NIMEngine(ManagedHTTPInferenceEngine):
    """Adapter for a pinned NVIDIA NIM LLM deployment profile."""

    name = "nim"
    readiness_path = "/v1/health/ready"

    def __init__(
        self, *args: Any, expected_release: str, profile_id: str, **kwargs: Any
    ):
        if not expected_release.strip() or not profile_id.strip():
            raise ValueError("NIM release and profile ID must be pinned.")
        self.expected_release = expected_release
        self.profile_id = profile_id
        super().__init__(*args, **kwargs)

    async def discover_model_identity(self) -> IdentityDiscovery:
        identity = await super().discover_model_identity()
        version = await self._json("GET", "/v1/version", "identity")
        metadata = await self._json("GET", "/v1/metadata", "identity")
        observed_release = self._find_string(version, "version", "nim_version")
        observed_profile = self._find_string(
            metadata, "profile_id", "model_profile", "model_profile_id"
        )
        if observed_release != self.expected_release:
            raise UpstreamProtocolFailure(
                context={"operation": "identity", "reason": "nim_release_mismatch"}
            )
        if observed_profile != self.profile_id:
            raise UpstreamProtocolFailure(
                context={"operation": "identity", "reason": "nim_profile_mismatch"}
            )
        adapter_metadata = dict(identity.adapter_metadata)
        adapter_metadata["nim"] = {
            "release": observed_release,
            "profile_id": observed_profile,
            "backend": self._find_string(metadata, "backend", "engine"),
        }
        return IdentityDiscovery(identity.observation, adapter_metadata)

    def _response_metadata(self, result: dict[str, Any]) -> dict[str, Any]:
        metadata = super()._response_metadata(result)
        metadata.update(
            {"release": self.expected_release, "profile_id": self.profile_id}
        )
        return metadata

    @staticmethod
    def _find_string(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None
