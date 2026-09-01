from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse


class AdvancedTaskKind(StrEnum):
    STRUCTURED_GENERATION = "structured_generation"
    TOOL_GENERATION = "tool_generation"
    MULTIMODAL_GENERATION = "multimodal_generation"
    EMBEDDING = "embedding"
    RERANK = "rerank"


@dataclass(frozen=True, slots=True)
class AdvancedCapabilityProfile:
    task_kinds: frozenset[AdvancedTaskKind]
    streaming: bool = False
    cancellation: bool = False
    structured_output: bool = False
    tool_calls: bool = False
    image_media_types: frozenset[str] = frozenset()


def advanced_capability_rejections(
    profile: AdvancedCapabilityProfile,
    task_kind: AdvancedTaskKind,
    *,
    requires_streaming: bool = False,
    requires_cancellation: bool = False,
    image_media_types: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    rejections: list[str] = []
    if task_kind not in profile.task_kinds:
        rejections.append("unsupported_task_kind")
    if requires_streaming and not profile.streaming:
        rejections.append("unsupported_streaming")
    if requires_cancellation and not profile.cancellation:
        rejections.append("unsupported_cancellation")
    if (
        task_kind is AdvancedTaskKind.STRUCTURED_GENERATION
        and not profile.structured_output
    ):
        rejections.append("unsupported_structured_output")
    if task_kind is AdvancedTaskKind.TOOL_GENERATION and not profile.tool_calls:
        rejections.append("unsupported_tool_calls")
    if not image_media_types.issubset(profile.image_media_types):
        rejections.append("unsupported_image_media_type")
    return tuple(rejections)


@dataclass(frozen=True, slots=True)
class JSONSchemaConstraint:
    schema: dict[str, Any]

    def __post_init__(self) -> None:
        if self.schema.get("type") != "object":
            raise ValueError(
                "The first structured-output slice requires an object schema."
            )
        properties = self.schema.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("Object schemas require a properties mapping.")
        required = self.schema.get("required", [])
        if not isinstance(required, list) or any(
            item not in properties for item in required
        ):
            raise ValueError("Schema required fields must name declared properties.")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    arguments: JSONSchemaConstraint

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError("Tool names must be non-empty alphanumeric identifiers.")
        if not self.description.strip():
            raise ValueError("Tool descriptions must not be blank.")


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImageInput:
    media_type: str
    uri: str

    def __post_init__(self) -> None:
        if self.media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unsupported image media type.")
        parsed = urlparse(self.uri)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
            raise ValueError("Images require an HTTPS object URI without credentials.")


@dataclass(frozen=True, slots=True)
class MultimodalInput:
    text: str
    images: tuple[ImageInput, ...]

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.images:
            raise ValueError("Multimodal input requires text and at least one image.")
        if len(self.images) > 8:
            raise ValueError("At most eight images are allowed per task.")


@dataclass(frozen=True, slots=True)
class StructuredOutput:
    value: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCallsOutput:
    calls: tuple[ToolCall, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingTask:
    texts: tuple[str, ...]
    model: str

    def __post_init__(self) -> None:
        if not self.texts or len(self.texts) > 256:
            raise ValueError("Embedding batches must contain between 1 and 256 texts.")
        if any(not value.strip() for value in self.texts) or not self.model.strip():
            raise ValueError("Embedding text and model values must not be blank.")


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vectors: tuple[tuple[float, ...], ...]
    model: str

    def __post_init__(self) -> None:
        if not self.vectors or any(not vector for vector in self.vectors):
            raise ValueError("Embedding vectors must not be empty.")
        dimensions = {len(vector) for vector in self.vectors}
        if len(dimensions) != 1:
            raise ValueError("All embedding vectors must have equal dimensions.")


@dataclass(frozen=True, slots=True)
class RerankTask:
    query: str
    documents: tuple[str, ...]
    model: str
    top_n: int | None = None

    def __post_init__(self) -> None:
        if not self.query.strip() or not self.model.strip() or not self.documents:
            raise ValueError("Reranking requires a query, model, and documents.")
        if any(not value.strip() for value in self.documents):
            raise ValueError("Reranking documents must not be blank.")
        if self.top_n is not None and not 1 <= self.top_n <= len(self.documents):
            raise ValueError("top_n must fit the document collection.")


@dataclass(frozen=True, slots=True)
class RerankItem:
    document_index: int
    score: float


@dataclass(frozen=True, slots=True)
class RerankResult:
    items: tuple[RerankItem, ...]
    model: str

    def __post_init__(self) -> None:
        if (
            tuple(
                sorted(self.items, key=lambda item: (-item.score, item.document_index))
            )
            != self.items
        ):
            raise ValueError("Rerank results must have deterministic descending order.")


class StreamEventKind(StrEnum):
    START = "start"
    DELTA = "delta"
    END = "end"


@dataclass(frozen=True, slots=True)
class InferenceStreamEvent:
    sequence: int
    kind: StreamEventKind
    text_delta: str = ""

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("Stream sequence cannot be negative.")
        if self.kind is StreamEventKind.DELTA and not self.text_delta:
            raise ValueError("Delta events require text.")
        if self.kind is not StreamEventKind.DELTA and self.text_delta:
            raise ValueError("Only delta events may carry text.")


class CancellationToken:
    """Cooperative cancellation primitive passed through Ryuk-owned contracts."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


def validate_json_schema(
    value: object, constraint: JSONSchemaConstraint
) -> tuple[str, ...]:
    """Validate Ryuk's deliberately small, deterministic JSON-schema subset."""
    if not isinstance(value, dict):
        return ("root:not_object",)
    schema = constraint.schema
    properties: dict[str, Any] = schema["properties"]
    errors: list[str] = []
    for name in schema.get("required", []):
        if name not in value:
            errors.append(f"{name}:required")
    if schema.get("additionalProperties") is False:
        errors.extend(
            f"{name}:additional_property" for name in value if name not in properties
        )
    python_types: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for name, item in value.items():
        property_schema = properties.get(name)
        if not isinstance(property_schema, dict) or "type" not in property_schema:
            continue
        expected = python_types.get(property_schema["type"])
        if expected is not None and (
            not isinstance(item, expected)
            or isinstance(item, bool)
            and property_schema["type"] in {"integer", "number"}
        ):
            errors.append(f"{name}:wrong_type")
    return tuple(errors)
