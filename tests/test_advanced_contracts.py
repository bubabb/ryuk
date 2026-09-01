import pytest

from backend.inference.advanced import (
    AdvancedCapabilityProfile,
    AdvancedTaskKind,
    CancellationToken,
    EmbeddingResult,
    EmbeddingTask,
    ImageInput,
    InferenceStreamEvent,
    JSONSchemaConstraint,
    MultimodalInput,
    RerankItem,
    RerankResult,
    RerankTask,
    StreamEventKind,
    ToolDefinition,
    advanced_capability_rejections,
    validate_json_schema,
)


def schema() -> JSONSchemaConstraint:
    return JSONSchemaConstraint(
        {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
    )


def test_structured_output_schema_is_deterministically_validated() -> None:
    assert validate_json_schema({"answer": "yes"}, schema()) == ()
    assert validate_json_schema({"extra": 1}, schema()) == (
        "answer:required",
        "extra:additional_property",
    )


def test_tool_calls_are_representation_only() -> None:
    tool = ToolDefinition("lookup_fact", "Find one fact", schema())
    assert tool.name == "lookup_fact"
    assert not hasattr(tool, "execute")


def test_multimodal_slice_rejects_unsafe_or_unsupported_uris() -> None:
    value = MultimodalInput(
        "Describe", (ImageInput("image/png", "https://assets.example/image.png"),)
    )
    assert value.images[0].media_type == "image/png"
    with pytest.raises(ValueError):
        ImageInput("image/svg+xml", "https://assets.example/image.svg")
    with pytest.raises(ValueError):
        ImageInput("image/png", "file:///etc/passwd")


def test_embedding_and_rerank_are_separate_task_types() -> None:
    task = EmbeddingTask(("one", "two"), "embed-model")
    result = EmbeddingResult(((0.1, 0.2), (0.3, 0.4)), "embed-model")
    assert len(task.texts) == len(result.vectors)
    rerank = RerankTask("query", ("a", "b"), "rerank-model", top_n=1)
    ranked = RerankResult((RerankItem(1, 0.9), RerankItem(0, 0.1)), rerank.model)
    assert ranked.items[0].document_index == 1


@pytest.mark.asyncio
async def test_stream_events_and_cancellation_are_explicit() -> None:
    token = CancellationToken()
    event = InferenceStreamEvent(1, StreamEventKind.DELTA, "hello")
    assert event.text_delta == "hello"
    token.cancel()
    await token.wait()
    assert token.cancelled


def test_advanced_capabilities_fail_closed() -> None:
    profile = AdvancedCapabilityProfile(
        frozenset({AdvancedTaskKind.MULTIMODAL_GENERATION}),
        image_media_types=frozenset({"image/png"}),
    )
    assert advanced_capability_rejections(
        profile,
        AdvancedTaskKind.MULTIMODAL_GENERATION,
        requires_streaming=True,
        image_media_types=frozenset({"image/webp"}),
    ) == ("unsupported_streaming", "unsupported_image_media_type")
