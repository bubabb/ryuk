from backend.inference.base import InferenceRequest
from backend.inference.contracts import InferenceTask, TextInput
from backend.inference.errors import UnsupportedTaskFailure


class LegacyAdapterUnsupportedTaskError(UnsupportedTaskFailure):
    """A typed task cannot be represented by the legacy adapter contract."""


def task_to_legacy_request(task: InferenceTask) -> InferenceRequest:
    """Translate the typed text contract during incremental adapter migration."""

    if not isinstance(task.input, TextInput):
        raise LegacyAdapterUnsupportedTaskError()

    metadata = {"request_id": task.trace.request_id}
    if task.trace.traceparent is not None:
        metadata["traceparent"] = task.trace.traceparent

    return InferenceRequest(
        prompt=task.input.text,
        model=task.requirements.requested_model or "",
        max_tokens=task.generation.max_output_tokens,
        temperature=task.generation.temperature,
        metadata=metadata,
    )
