from abc import ABC, abstractmethod

from dataclasses import dataclass, field

from typing import Any

@dataclass

class InferenceRequest:

    prompt: str

    model: str

    max_tokens: int | None = None

    temperature: float = 0.7

    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass

class InferenceResponse:

    text: str

    model: str

    engine: str

    latency_ms: float | None = None

    input_tokens: int | None = None

    output_tokens: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

class InferenceEngine(ABC):

    """

    Base contract for every inference backend supported by Ryuk.

    Implementations may use SGLang, vLLM, TensorRT-LLM, Dynamo, NIM,

    or future inference systems without changing the rest of Ryuk.

    """

    name: str

    @abstractmethod

    async def is_available(self) -> bool:

        """Return True when this engine is ready to accept inference requests."""

        raise NotImplementedError

    @abstractmethod

    async def generate(self, request: InferenceRequest) -> InferenceResponse:

        """Run inference and return a normalized Ryuk response."""

        raise NotImplementedError

    async def health(self) -> dict[str, Any]:

        available = await self.is_available()

        return {

            "engine": self.name,

            "available": available,

        }