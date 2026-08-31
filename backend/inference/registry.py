from __future__ import annotations

from typing import Iterable

from backend.config import settings

from backend.inference.base import InferenceEngine

from backend.inference.engines.sglang import SGLangEngine

from backend.inference.engines.mock import MockEngine

from backend.inference.engines.mock import MockEngine
from backend.inference.engines.sglang import SGLangEngine

class EngineRegistry:

    """

    Stores and manages inference engines available to Ryuk.

    """

    def __init__(self) -> None:

        self._engines: dict[str, InferenceEngine] = {}

    def register(self, engine: InferenceEngine) -> None:

        name = engine.name.strip().lower()

        if not name:

            raise ValueError("Inference engine must define a non-empty name.")

        self._engines[name] = engine

    def unregister(self, name: str) -> None:

        self._engines.pop(name.strip().lower(), None)

    def get(self, name: str) -> InferenceEngine:

        key = name.strip().lower()

        try:

            return self._engines[key]

        except KeyError as exc:

            available = ", ".join(sorted(self._engines)) or "none"

            raise KeyError(

                f"Inference engine '{name}' is not registered. "

                f"Registered engines: {available}"

            ) from exc

    def all(self) -> tuple[InferenceEngine, ...]:

        return tuple(self._engines.values())

    def names(self) -> tuple[str, ...]:

        return tuple(sorted(self._engines))

    def register_many(self, engines: Iterable[InferenceEngine]) -> None:

        for engine in engines:

            self.register(engine)

    def __contains__(self, name: str) -> bool:

        return name.strip().lower() in self._engines

    def __len__(self) -> int:

        return len(self._engines)

def build_engine_registry() -> EngineRegistry:

    """

    Build Ryuk's inference engine registry from application settings.

    Only engines explicitly enabled in configuration are registered.

    """

    registry = EngineRegistry()

    if settings.sglang_enabled:

        registry.register(

            SGLangEngine(

                base_url=settings.sglang_base_url,

            )

        )

    if settings.mock_enabled:

        registry.register(MockEngine())

    return registry

    # Future native adapters:

    #

    # if settings.vllm_enabled:

    #     registry.register(VLLMEngine(...))

    #

    # if settings.tensorrt_llm_enabled:

    #     registry.register(TensorRTLLMEngine(...))

    #

    # if settings.dynamo_enabled:

    #     registry.register(DynamoEngine(...))

    #

    # if settings.nim_enabled:

    #     registry.register(NIMEngine(...))

    return registry