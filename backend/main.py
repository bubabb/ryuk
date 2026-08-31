from fastapi import FastAPI, HTTPException

from pydantic import BaseModel

from backend.config import settings

from backend.inference.base import InferenceRequest

from backend.inference.registry import build_engine_registry

from backend.inference.router import (

    InferenceRouter,

    NoAvailableEngineError,

)

app = FastAPI(

    title=settings.app_name,

    version=settings.app_version,

)

engine_registry = build_engine_registry()

inference_router = InferenceRouter(engine_registry)

class GenerateRequest(BaseModel):

    prompt: str

    model: str

    preferred_engine: str | None = None

    max_tokens: int | None = None

    temperature: float = 0.7

@app.get("/health")

def health():

    return {

        "status": "ok",

        "service": settings.app_name,

        "environment": settings.app_env,

    }

@app.get("/inference/engines")

async def inference_engines():

    engines = []

    for engine in engine_registry.all():

        engines.append(

            {

                "name": engine.name,

                "available": await engine.is_available(),

            }

        )

    return {

        "count": len(engines),

        "engines": engines,

    }

@app.post("/inference/generate")

async def inference_generate(payload: GenerateRequest):

    request = InferenceRequest(

        prompt=payload.prompt,

        model=payload.model,

        max_tokens=payload.max_tokens,

        temperature=payload.temperature,

    )

    try:

        response = await inference_router.generate(

            request,

            preferred_engine=payload.preferred_engine,

        )

    except NoAvailableEngineError as exc:

        raise HTTPException(

            status_code=503,

            detail=str(exc),

        ) from exc

    except KeyError as exc:

        raise HTTPException(

            status_code=400,

            detail=str(exc),

        ) from exc

    return {

        "text": response.text,

        "model": response.model,

        "engine": response.engine,

        "latency_ms": response.latency_ms,

        "input_tokens": response.input_tokens,

        "output_tokens": response.output_tokens,

        "metadata": response.metadata,

    }