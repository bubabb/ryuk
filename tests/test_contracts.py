from datetime import UTC, datetime

import pytest

from backend.inference.base import DeploymentProvenance
from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    FinishReason,
    GenerationConfig,
    InferenceResult,
    InferenceTask,
    InferenceTiming,
    TaskRequirements,
    TextInput,
    TextOutput,
    TokenUsage,
    TraceContext,
)
from backend.inference.deployment import IdentityVerification


def test_text_task_keeps_generation_and_requirements_separate() -> None:
    task = InferenceTask(
        input=TextInput("Explain Ryuk"),
        generation=GenerationConfig(max_output_tokens=100, temperature=0.2),
        requirements=TaskRequirements(requested_model="moonshotai/Kimi-K2"),
        trace=TraceContext(request_id="request-1"),
        deadline_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert task.input == TextInput("Explain Ryuk")
    assert task.generation.max_output_tokens == 100
    assert task.requirements.requested_model == "moonshotai/Kimi-K2"


def test_chat_preserves_ordered_typed_messages() -> None:
    chat = ChatInput(
        messages=(
            ChatMessage(ChatRole.SYSTEM, "Be concise."),
            ChatMessage(ChatRole.USER, "Explain Ryuk."),
        )
    )

    assert [message.role for message in chat.messages] == [
        ChatRole.SYSTEM,
        ChatRole.USER,
    ]


@pytest.mark.parametrize("value", ["", "   "])
def test_text_input_rejects_empty_content(value: str) -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        TextInput(value)


def test_chat_requires_at_least_one_message() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ChatInput(messages=())


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_generation_rejects_invalid_temperature(temperature: float) -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationConfig(temperature=temperature)


def test_generation_rejects_non_positive_token_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        GenerationConfig(max_output_tokens=0)


def test_task_deadline_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        InferenceTask(
            input=TextInput("hello"),
            generation=GenerationConfig(),
            requirements=TaskRequirements(),
            trace=TraceContext(request_id="request-1"),
            deadline_at=datetime(2026, 9, 1),
        )


def test_unknown_usage_is_distinct_from_zero() -> None:
    assert TokenUsage().input_tokens is None
    assert TokenUsage(input_tokens=0).input_tokens == 0


def test_negative_usage_and_timing_are_rejected() -> None:
    with pytest.raises(ValueError, match="input_tokens"):
        TokenUsage(input_tokens=-1)
    with pytest.raises(ValueError, match="total_ms"):
        InferenceTiming(total_ms=-0.1)


def test_result_requires_deployment_provenance() -> None:
    provenance = DeploymentProvenance(
        deployment_id="mock-development",
        engine_name="mock",
        model_artifact_id="ryuk/mock",
        model_revision=None,
        model_verification=IdentityVerification.VERIFIED,
        serving_runtime="in_process",
    )

    result = InferenceResult(
        output=TextOutput("result"),
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(),
        timing=InferenceTiming(total_ms=1.0),
        provenance=provenance,
        adapter_metadata={},
    )

    assert result.provenance.deployment_id == "mock-development"
