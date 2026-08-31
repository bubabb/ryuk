from backend.inference.base import (

    InferenceEngine,

    InferenceRequest,

    InferenceResponse,

)

class MockEngine(InferenceEngine):

    name = "mock"

    async def is_available(self) -> bool:

        return True

    async def generate(

        self,

        request: InferenceRequest,

    ) -> InferenceResponse:

        return InferenceResponse(

            text=f"Mock response for: {request.prompt}",

            model=request.model,

            engine=self.name,

            latency_ms=1.0,

            input_tokens=None,

            output_tokens=None,

            metadata={

                "mock": True,

            },

        )