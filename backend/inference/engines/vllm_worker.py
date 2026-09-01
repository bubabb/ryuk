from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from backend.inference.base import InferenceEngine, InferenceRequest, InferenceResponse
from backend.inference.contracts import (
    AdapterInferenceResult,
    ChatInput,
    FinishReason,
    InferenceTask,
    InferenceTiming,
    TextInput,
    TextOutput,
    TokenUsage,
)
from backend.inference.deployment import (
    IdentityDiscovery,
    ModelIdentityObservation,
    ModelRef,
)
from backend.inference.errors import (
    CapacityExceededFailure,
    DeadlineExceededFailure,
    DeploymentUnavailableFailure,
    GenerationFailure,
    UpstreamProtocolFailure,
)


class VLLMWorkerEngine(InferenceEngine):
    """Controller-side adapter for Ryuk's native vLLM worker contract."""

    name = "vllm"

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 120.0,
        client: httpx.AsyncClient | None = None,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.max_response_bytes = max_response_bytes
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=5.0, pool=5.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(f"{self.base_url}/ryuk/v1/health")
            return response.status_code == 200 and response.json().get("ready") is True
        except (httpx.HTTPError, ValueError):
            return False

    async def discover_model_identity(self) -> IdentityDiscovery:
        result = await self._json("GET", "/ryuk/v1/identity", "identity")
        artifact = result.get("model_artifact_id")
        revision = result.get("model_revision")
        if not isinstance(artifact, str) or not artifact:
            raise UpstreamProtocolFailure(
                context={"operation": "identity", "reason": "invalid_schema"}
            )
        if revision is not None and not isinstance(revision, str):
            raise UpstreamProtocolFailure(
                context={"operation": "identity", "reason": "invalid_schema"}
            )
        from datetime import UTC, datetime

        return IdentityDiscovery(
            observation=ModelIdentityObservation(
                model=ModelRef(artifact, revision=revision),
                observed_at=datetime.now(UTC),
                source="vllm-worker:/ryuk/v1/identity",
            ),
            adapter_metadata={"worker_identity": result},
        )

    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult:
        if isinstance(task.input, TextInput):
            input_payload: dict[str, Any] = {
                "kind": "text",
                "text": task.input.text,
            }
        elif isinstance(task.input, ChatInput):
            input_payload = {
                "kind": "chat",
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in task.input.messages
                ],
            }
        else:  # pragma: no cover
            raise TypeError("Unsupported input type.")
        payload = {
            "request_id": task.trace.request_id,
            "input": input_payload,
            "generation": {
                "max_output_tokens": task.generation.max_output_tokens,
                "temperature": task.generation.temperature,
            },
        }
        started = time.perf_counter()
        try:
            result = await self._json(
                "POST", "/ryuk/v1/generate", "generation", json=payload
            )
        except asyncio.CancelledError:
            try:
                await asyncio.shield(
                    self._client.delete(
                        f"{self.base_url}/ryuk/v1/requests/{task.trace.request_id}"
                    )
                )
            finally:
                raise
        text = result.get("text")
        finish = result.get("finish_reason", "unknown")
        usage = result.get("usage", {})
        if not isinstance(text, str) or not isinstance(usage, dict):
            raise self._protocol()
        try:
            finish_reason = FinishReason(finish)
        except ValueError:
            finish_reason = FinishReason.UNKNOWN
        return AdapterInferenceResult(
            output=TextOutput(text),
            finish_reason=finish_reason,
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            ),
            timing=InferenceTiming(
                total_ms=result.get("latency_ms")
                or (time.perf_counter() - started) * 1000
            ),
            adapter_metadata={"vllm_worker": result.get("metadata", {})},
        )

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        del request
        raise NotImplementedError("Use the typed vLLM worker contract.")

    async def _json(
        self,
        method: str,
        path: str,
        operation: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            async with self._client.stream(
                method, f"{self.base_url}{path}", **kwargs
            ) as response:
                context = {"operation": operation, "status": response.status_code}
                if response.status_code in {429, 503}:
                    raise CapacityExceededFailure(context=context)
                if response.status_code in {408, 504}:
                    raise DeadlineExceededFailure(context=context)
                if response.status_code >= 500:
                    raise GenerationFailure(context=context)
                if not response.is_success:
                    raise UpstreamProtocolFailure(context=context)
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
            failure = (
                DeadlineExceededFailure
                if operation == "generation"
                else DeploymentUnavailableFailure
            )
            raise failure(context={"operation": operation}) from exc
        except httpx.TransportError as exc:
            raise DeploymentUnavailableFailure(
                context={"operation": operation}
            ) from exc
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise self._protocol() from exc
        if not isinstance(result, dict):
            raise self._protocol()
        return result

    @staticmethod
    def _protocol() -> UpstreamProtocolFailure:
        return UpstreamProtocolFailure(
            context={"operation": "generation", "reason": "invalid_schema"}
        )
