from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from backend.inference.base import DeploymentProvenance


def _require_text(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must contain non-whitespace text.")


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class TextInput:
    text: str

    def __post_init__(self) -> None:
        _require_text(self.text, "text")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        _require_text(self.content, "content")


@dataclass(frozen=True, slots=True)
class ChatInput:
    messages: tuple[ChatMessage, ...]

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("Chat input must contain at least one message.")


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    max_output_tokens: int | None = None
    temperature: float = 0.7

    def __post_init__(self) -> None:
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive when provided.")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0.")


@dataclass(frozen=True, slots=True)
class RoutingRequirements:
    requested_model: str | None = None
    required_model: str | None = None
    required_context_tokens: int | None = None
    requires_structured_output: bool = False
    requires_streaming: bool = False
    required_accelerator: str | None = None
    required_topology: str | None = None
    required_data_location: str | None = None
    production_only: bool = False

    def __post_init__(self) -> None:
        for field_name in ("requested_model", "required_model"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        if (
            self.required_context_tokens is not None
            and self.required_context_tokens < 1
        ):
            raise ValueError("required_context_tokens must be positive.")
        for field_name in (
            "required_accelerator",
            "required_topology",
            "required_data_location",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)


TaskRequirements = RoutingRequirements


@dataclass(frozen=True, slots=True)
class TraceContext:
    request_id: str
    traceparent: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")


@dataclass(frozen=True, slots=True)
class InferenceTask:
    input: TextInput | ChatInput
    generation: GenerationConfig
    requirements: RoutingRequirements
    trace: TraceContext
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.deadline_at is not None and (
            self.deadline_at.tzinfo is None or self.deadline_at.utcoffset() is None
        ):
            raise ValueError("deadline_at must include timezone information.")


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"
    UNKNOWN = "unknown"


class AttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    attempt_id: str
    sequence: int
    deployment_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    outcome: AttemptOutcome
    failure_code: str | None = None
    retry_classification: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.attempt_id, "attempt_id")
        _require_text(self.deployment_id, "deployment_id")
        if self.sequence < 1:
            raise ValueError("sequence must be positive.")
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative.")
        for value in (self.started_at, self.finished_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    "attempt timestamps must include timezone information."
                )
        if self.outcome is AttemptOutcome.SUCCEEDED and self.failure_code is not None:
            raise ValueError("A successful attempt cannot contain a failure code.")
        if self.outcome is AttemptOutcome.FAILED and self.failure_code is None:
            raise ValueError("A failed attempt must contain a failure code.")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative.")


@dataclass(frozen=True, slots=True)
class InferenceTiming:
    total_ms: float | None = None

    def __post_init__(self) -> None:
        if self.total_ms is not None and self.total_ms < 0:
            raise ValueError("total_ms cannot be negative.")


@dataclass(frozen=True, slots=True)
class TextOutput:
    text: str


@dataclass(frozen=True, slots=True)
class AdapterInferenceResult:
    """Typed adapter output before router-owned provenance is attached."""

    output: TextOutput
    finish_reason: FinishReason
    usage: TokenUsage
    timing: InferenceTiming
    adapter_metadata: dict[str, Any]


@runtime_checkable
class TypedInferenceEngine(Protocol):
    async def generate_task(self, task: InferenceTask) -> AdapterInferenceResult: ...


@dataclass(frozen=True, slots=True)
class InferenceResult:
    output: TextOutput
    finish_reason: FinishReason
    usage: TokenUsage
    timing: InferenceTiming
    provenance: DeploymentProvenance
    adapter_metadata: dict[str, Any]
    attempts: tuple[ExecutionAttempt, ...] = ()
    routing_decision: RoutingDecision | None = None


@dataclass(frozen=True, slots=True)
class RoutingScore:
    deployment_id: str
    total: int
    components: tuple[tuple[str, int], ...]
    explanation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    policy_version: str
    ordered_deployment_ids: tuple[str, ...]
    candidates: tuple[RoutingScore, ...]
