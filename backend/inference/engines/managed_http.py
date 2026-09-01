from __future__ import annotations

import json
import time
from datetime import UTC, datetime
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


class ManagedHTTPInferenceEngine(InferenceEngine):
    """Contain a managed serving product's external HTTP protocol.

    This is adapter infrastructure, not a Ryuk-wide protocol. Subclasses own
    their documented endpoint choices and provenance discovery.
    """

    readiness_path: str
    models_path = "/v1/models"

    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        max_response_bytes: int = 16 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("A served model is required.")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_response_bytes = max_response_bytes
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=5.0, pool=5.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(
                f"{self.base_url}{self.readiness_path}", timeout=3.0
            )
            return response.is_success
        except httpx.HTTPError:
            return False

    async def discover_model_identity(self) -> IdentityDiscovery:
        result = await self._json("GET", self.models_path, "identity")
        data = result.get("data")
        if not isinstance(data, list):
            raise self._protocol("identity", "invalid_models_schema")
        model_ids = [item.get("id") for item in data if isinstance(item, dict)]
        if self.model not in model_ids:
            raise self._protocol("identity", "configured_model_not_served")
        return IdentityDiscovery(
            observation=ModelIdentityObservation(
                model=ModelRef(self.model, served_name=self.model),
                observed_at=datetime.now(UTC),
                source=f"{self.name}:{self.models_path}",
            ),
            adapter_metadata={"served_model_ids": model_ids},
        )

    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": task.generation.temperature,
            "stream": False,
        }
        if task.generation.max_output_tokens is not None:
            payload["max_tokens"] = task.generation.max_output_tokens
        if isinstance(task.input, TextInput):
            path = "/v1/completions"
            payload["prompt"] = task.input.text
        elif isinstance(task.input, ChatInput):
            path = "/v1/chat/completions"
            payload["messages"] = [
                {"role": message.role, "content": message.content}
                for message in task.input.messages
            ]
        else:  # pragma: no cover
            raise TypeError("Unsupported input type.")

        started = time.perf_counter()
        result = await self._json(
            "POST",
            path,
            "generation",
            json=payload,
            headers={"X-Request-Id": task.trace.request_id},
        )
        choices = result.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise self._protocol("generation", "invalid_choices")
        choice = choices[0]
        if isinstance(task.input, ChatInput):
            message = choice.get("message")
            text = message.get("content") if isinstance(message, dict) else None
        else:
            text = choice.get("text")
        if not isinstance(text, str):
            raise self._protocol("generation", "invalid_text")
        usage = result.get("usage") or {}
        if not isinstance(usage, dict):
            raise self._protocol("generation", "invalid_usage")
        return AdapterInferenceResult(
            output=TextOutput(text),
            finish_reason=self._finish_reason(choice.get("finish_reason")),
            usage=TokenUsage(
                input_tokens=self._optional_count(usage.get("prompt_tokens")),
                output_tokens=self._optional_count(usage.get("completion_tokens")),
            ),
            timing=InferenceTiming(total_ms=(time.perf_counter() - started) * 1000),
            adapter_metadata={self.name: self._response_metadata(result)},
        )

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        del request
        raise NotImplementedError(f"Use the typed {self.name} adapter contract.")

    def _response_metadata(self, result: dict[str, Any]) -> dict[str, Any]:
        return {"response_id": result.get("id"), "served_model": result.get("model")}

    async def _json(
        self, method: str, path: str, operation: str, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            async with self._client.stream(
                method, f"{self.base_url}{path}", **kwargs
            ) as response:
                self._raise_for_status(response.status_code, operation)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise self._protocol(operation, "response_too_large")
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
            raise self._protocol(operation, "invalid_json") from exc
        if not isinstance(result, dict):
            raise self._protocol(operation, "non_object_json")
        return result

    @staticmethod
    def _raise_for_status(status: int, operation: str) -> None:
        context = {"operation": operation, "status": status}
        if 200 <= status < 300:
            return
        if status in {429, 503}:
            raise CapacityExceededFailure(context=context)
        if status in {408, 504}:
            raise DeadlineExceededFailure(context=context)
        if status >= 500:
            raise GenerationFailure(context=context)
        raise UpstreamProtocolFailure(context=context)

    @staticmethod
    def _finish_reason(value: object) -> FinishReason:
        if not isinstance(value, str):
            return FinishReason.UNKNOWN
        try:
            return FinishReason(value)
        except ValueError:
            return FinishReason.UNKNOWN

    @staticmethod
    def _optional_count(value: object) -> int | None:
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )

    @staticmethod
    def _protocol(operation: str, reason: str) -> UpstreamProtocolFailure:
        return UpstreamProtocolFailure(
            context={"operation": operation, "reason": reason}
        )
