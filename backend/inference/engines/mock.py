from datetime import UTC, datetime

from backend.inference.base import (
    InferenceEngine,
    InferenceRequest,
    InferenceResponse,
)
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


class MockEngine(InferenceEngine):
    name = "mock"

    async def is_available(self) -> bool:
        return True

    async def discover_model_identity(self) -> IdentityDiscovery:
        return IdentityDiscovery(
            observation=ModelIdentityObservation(
                model=ModelRef(artifact_id="ryuk/mock", served_name="mock"),
                observed_at=datetime.now(UTC),
                source="mock:configuration",
            ),
            adapter_metadata={"mock": True},
        )

    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult:
        if isinstance(task.input, TextInput):
            text = f"Mock response for: {task.input.text}"
            input_kind = "text"
        elif isinstance(task.input, ChatInput):
            last_message = task.input.messages[-1]
            text = f"Mock chat response for: {last_message.content}"
            input_kind = "chat"
        else:  # pragma: no cover - protected by the closed input union
            raise TypeError("Unsupported mock input type.")

        return AdapterInferenceResult(
            output=TextOutput(text),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(),
            timing=InferenceTiming(total_ms=1.0),
            adapter_metadata={
                "mock": True,
                "production": False,
                "input_kind": input_kind,
                "warning": "Deterministic development output; no model executed.",
            },
        )

    async def generate(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        return InferenceResponse(
            text=f"Mock response for: {request.prompt}",
            model=request.model,
            engine=self.name,
            latency_ms=1.0,
            input_tokens=None,
            output_tokens=None,
            metadata={
                "mock": True,
                "production": False,
                "warning": "Deterministic development output; no model executed.",
            },
        )
