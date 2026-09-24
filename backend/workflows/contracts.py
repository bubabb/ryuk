"""Versioned workflow packets wrapping Ryuk's existing inference contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

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


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class TaskPacket:
    task: InferenceTask
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported task packet version")
        if not isinstance(self.task, InferenceTask):
            raise ValueError("Task packet requires an InferenceTask")
        self._validate_types()

    def to_dict(self) -> dict[str, Any]:
        task = asdict(self.task)
        task["input"]["kind"] = (
            "text" if isinstance(self.task.input, TextInput) else "chat"
        )
        task["deadline_at"] = (
            self.task.deadline_at.astimezone(UTC).isoformat()
            if self.task.deadline_at is not None
            else None
        )
        # Detach nested objects and normalize tuples/enums into JSON values.
        return json.loads(
            canonical_json({"schema_version": self.schema_version, "task": task})
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TaskPacket:
        try:
            if set(value) != {"schema_version", "task"}:
                raise ValueError("Invalid task packet fields")
            task = dict(value["task"])
            content = dict(task.pop("input"))
            kind = content.pop("kind")
            input_value: TextInput | ChatInput
            if kind == "text":
                input_value = TextInput(**content)
            elif kind == "chat" and set(content) == {"messages"}:
                input_value = ChatInput(
                    tuple(
                        ChatMessage(
                            role=ChatRole(message["role"]), content=message["content"]
                        )
                        for message in content["messages"]
                    )
                )
                if any(
                    set(message) != {"role", "content"}
                    for message in content["messages"]
                ):
                    raise ValueError("Invalid message fields")
            else:
                raise ValueError("Unsupported packet input")
            deadline = task.pop("deadline_at")
            packet = cls(
                InferenceTask(
                    input=input_value,
                    generation=GenerationConfig(**task.pop("generation")),
                    requirements=TaskRequirements(**task.pop("requirements")),
                    trace=TraceContext(**task.pop("trace")),
                    deadline_at=datetime.fromisoformat(deadline)
                    if deadline is not None
                    else None,
                    **task,
                ),
                schema_version=value["schema_version"],
            )
            # Canonical comparison rejects ignored fields and lossy shapes.
            if canonical_json(packet.to_dict()) != canonical_json(value):
                raise ValueError("Noncanonical task packet")
            return packet
        except (TypeError, KeyError, AttributeError, ValueError) as exc:
            raise ValueError("Invalid workflow task packet") from exc

    def _validate_types(self) -> None:
        task = self.task
        for value in (
            task.generation.max_output_tokens,
            task.requirements.required_context_tokens,
        ):
            if value is not None and type(value) is not int:
                raise ValueError("Token limits must be integers")
        if type(task.generation.temperature) not in (int, float):
            raise ValueError("Temperature must be numeric")
        for name, value in asdict(task.requirements).items():
            if name.startswith("requires_") or name == "production_only":
                if type(value) is not bool:
                    raise ValueError("Requirements flags must be booleans")
            elif (
                name != "required_context_tokens"
                and value is not None
                and not isinstance(value, str)
            ):
                raise ValueError("Requirement identifiers must be strings")
        if not isinstance(task.trace.request_id, str) or (
            task.trace.traceparent is not None
            and not isinstance(task.trace.traceparent, str)
        ):
            raise ValueError("Trace identifiers must be strings")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    workflow_id: str
    sha256: str
    size_bytes: int
    schema_version: int = 1
    media_type: str = "application/json"


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    ref: ArtifactRef
    content_json: str

    def __post_init__(self) -> None:
        data = self.content_json.encode("utf-8")
        if (
            self.ref.schema_version != 1
            or self.ref.media_type != "application/json"
            or len(data) != self.ref.size_bytes
            or hashlib.sha256(data).hexdigest() != self.ref.sha256
        ):
            raise ValueError("Workflow artifact integrity check failed")
        if not isinstance(json.loads(self.content_json), dict):
            raise ValueError("Artifact must contain a JSON object")

    def payload(self) -> dict[str, Any]:
        return json.loads(self.content_json)
