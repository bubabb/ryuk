import pytest

from backend.inference.compat import (
    LegacyAdapterUnsupportedTaskError,
    task_to_legacy_request,
)
from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)


def test_typed_text_task_translates_to_legacy_request() -> None:
    task = InferenceTask(
        input=TextInput("hello"),
        generation=GenerationConfig(max_output_tokens=20, temperature=0.1),
        requirements=TaskRequirements(requested_model="requested-model"),
        trace=TraceContext(
            request_id="request-1",
            traceparent=("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
        ),
    )

    request = task_to_legacy_request(task)

    assert request.prompt == "hello"
    assert request.model == "requested-model"
    assert request.max_tokens == 20
    assert request.temperature == 0.1
    assert request.metadata == {
        "request_id": "request-1",
        "traceparent": ("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
    }


def test_chat_is_not_flattened_into_legacy_text() -> None:
    task = InferenceTask(
        input=ChatInput(messages=(ChatMessage(ChatRole.USER, "hello"),)),
        generation=GenerationConfig(),
        requirements=TaskRequirements(),
        trace=TraceContext(request_id="request-1"),
    )

    with pytest.raises(LegacyAdapterUnsupportedTaskError) as raised:
        task_to_legacy_request(task)

    assert raised.value.code == "unsupported_task"
    assert str(raised.value) == "The selected deployment does not support this task."
