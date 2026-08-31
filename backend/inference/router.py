from __future__ import annotations

from backend.inference.base import (

    InferenceEngine,

    InferenceRequest,

    InferenceResponse,

)

from backend.inference.registry import EngineRegistry

class NoAvailableEngineError(RuntimeError):

    """Raised when Ryuk cannot find an available inference engine."""

class InferenceRouter:

    """

    Selects an available inference engine and sends the request to it.

    This is the first routing layer. Later, Ryuk will rank engines using

    task type, model compatibility, accuracy, latency, cost, context size,

    hardware availability, and historical performance.

    """

    def __init__(self, registry: EngineRegistry) -> None:

        self.registry = registry

    async def select_engine(

        self,

        preferred_engine: str | None = None,

    ) -> InferenceEngine:

        if preferred_engine is not None:

            engine = self.registry.get(preferred_engine)

            if await engine.is_available():

                return engine

        for engine in self.registry.all():

            if preferred_engine and engine.name.lower() == preferred_engine.lower():

                continue

            if await engine.is_available():

                return engine

        raise NoAvailableEngineError(

            "No registered inference engine is currently available."

        )

    async def generate(

        self,

        request: InferenceRequest,

        preferred_engine: str | None = None,

    ) -> InferenceResponse:

        engine = await self.select_engine(preferred_engine)

        return await engine.generate(request)