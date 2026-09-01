from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.inference.base import InferenceEngine, InferenceRequest, InferenceResponse
from backend.inference.deployment import (
    IdentityAssessment,
    IdentityDiscovery,
    IdentityDiscoveryFailure,
    ModelIdentityObservation,
    ModelRef,
    assess_model_identity,
)
from backend.inference.errors import (
    CapacityExceededFailure,
    DeadlineExceededFailure,
    DeploymentUnavailableFailure,
    GenerationFailure,
    UpstreamProtocolFailure,
)


class SGLangIdentityDiscoveryError(IdentityDiscoveryFailure):
    """SGLang identity response did not satisfy Ryuk's contract."""


class SGLangEngine(InferenceEngine):
    """Lifecycle-managed adapter for SGLang's native HTTP API."""

    name = "sglang"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:30000",
        *,
        connect_timeout: float = 5.0,
        read_timeout: float = 120.0,
        write_timeout: float = 10.0,
        pool_timeout: float = 5.0,
        identity_timeout: float = 3.0,
        max_response_bytes: int = 16 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive.")
        self.base_url = base_url.rstrip("/")
        self.identity_timeout = identity_timeout
        self.max_response_bytes = max_response_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=write_timeout,
                pool=pool_timeout,
            ),
        )

    async def __aenter__(self) -> SGLangEngine:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(
                f"{self.base_url}/health", timeout=httpx.Timeout(3.0)
            )
            return response.is_success
        except httpx.HTTPError:
            return False

    async def discover_model_identity(
        self,
        *,
        use_weight_version_as_revision: bool = False,
    ) -> IdentityDiscovery:
        result = await self._request_json(
            "GET",
            "/model_info",
            operation="identity",
            timeout=httpx.Timeout(self.identity_timeout),
        )
        model_path = self._optional_model_info_string(result, "model_path")
        if model_path is None:
            raise SGLangIdentityDiscoveryError(
                context={"operation": "identity", "reason": "missing_model_path"}
            )
        served_name = self._optional_model_info_string(result, "served_model_name")
        revision = self._optional_model_info_string(result, "weight_version")
        observation = ModelIdentityObservation(
            model=ModelRef(
                artifact_id=model_path,
                revision=revision if use_weight_version_as_revision else None,
                served_name=served_name,
            ),
            observed_at=datetime.now(UTC),
            source="sglang:/model_info",
        )
        return IdentityDiscovery(
            observation=observation, adapter_metadata={"model_info": result}
        )

    async def assess_model_identity(
        self,
        expected: ModelRef | None,
        *,
        use_weight_version_as_revision: bool = False,
    ) -> IdentityAssessment:
        discovery = await self.discover_model_identity(
            use_weight_version_as_revision=use_weight_version_as_revision
        )
        return assess_model_identity(expected, discovery.observation)

    async def generate(self, inference_request: InferenceRequest) -> InferenceResponse:
        sampling: dict[str, Any] = {"temperature": inference_request.temperature}
        if inference_request.max_tokens is not None:
            sampling["max_new_tokens"] = inference_request.max_tokens
        payload: dict[str, Any] = {
            "text": inference_request.prompt,
            "sampling_params": sampling,
        }
        request_id = inference_request.metadata.get("request_id")
        if isinstance(request_id, str) and request_id:
            payload["rid"] = request_id
        started = time.perf_counter()
        result = await self._request_json(
            "POST", "/generate", operation="generation", json_body=payload
        )
        text = result.get("text")
        meta = result.get("meta_info", {})
        if not isinstance(text, str) or not isinstance(meta, dict):
            raise self._schema_failure()
        input_tokens = self._optional_nonnegative_int(meta, "prompt_tokens")
        output_tokens = self._optional_nonnegative_int(meta, "completion_tokens")
        finish_reason = meta.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise self._schema_failure()
        return InferenceResponse(
            text=text,
            model=inference_request.model,
            engine=self.name,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata={"sglang_meta": meta, "sglang_finish_reason": finish_reason},
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json_body: dict[str, Any] | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> dict[str, Any]:
        try:
            if timeout is None:
                stream = self._client.stream(
                    method, f"{self.base_url}{path}", json=json_body
                )
            else:
                stream = self._client.stream(
                    method,
                    f"{self.base_url}{path}",
                    json=json_body,
                    timeout=timeout,
                )
            async with stream as response:
                self._raise_for_status(response.status_code, operation)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise UpstreamProtocolFailure(
                            context={
                                "operation": operation,
                                "reason": "response_too_large",
                            }
                        )
        except httpx.TimeoutException as exc:
            timeout_failure = (
                DeadlineExceededFailure
                if operation == "generation"
                else DeploymentUnavailableFailure
            )
            raise timeout_failure(context={"operation": operation}) from exc
        except httpx.TransportError as exc:
            raise DeploymentUnavailableFailure(
                context={"operation": operation}
            ) from exc
        try:
            result = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            protocol_failure = (
                UpstreamProtocolFailure
                if operation == "generation"
                else SGLangIdentityDiscoveryError
            )
            raise protocol_failure(
                context={"operation": operation, "reason": "invalid_json"}
            ) from exc
        if not isinstance(result, dict):
            schema_failure = (
                UpstreamProtocolFailure
                if operation == "generation"
                else SGLangIdentityDiscoveryError
            )
            raise schema_failure(
                context={"operation": operation, "reason": "non_object_json"}
            )
        return result

    @staticmethod
    def _raise_for_status(status: int, operation: str) -> None:
        context = {"operation": operation, "status": status}
        if 200 <= status < 300:
            return
        if operation == "identity":
            failure = (
                DeploymentUnavailableFailure
                if status in {429, 503}
                else SGLangIdentityDiscoveryError
            )
            raise failure(context=context)
        if status in {429, 503}:
            raise CapacityExceededFailure(context=context)
        if status in {408, 504}:
            raise DeadlineExceededFailure(context=context)
        if status >= 500:
            raise GenerationFailure(context=context)
        raise UpstreamProtocolFailure(context=context)

    @staticmethod
    def _optional_model_info_string(
        result: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = result.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value or value != value.strip():
            raise SGLangIdentityDiscoveryError(
                context={
                    "operation": "identity",
                    "reason": "invalid_field",
                    "field": field_name,
                }
            )
        return value

    @staticmethod
    def _optional_nonnegative_int(meta: dict[str, Any], field: str) -> int | None:
        value = meta.get(field)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SGLangEngine._schema_failure()
        return value

    @staticmethod
    def _schema_failure() -> UpstreamProtocolFailure:
        return UpstreamProtocolFailure(
            context={"operation": "generation", "reason": "invalid_schema"}
        )
