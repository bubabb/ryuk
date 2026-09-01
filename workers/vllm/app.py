"""Linux/NVIDIA-only Ryuk worker. This module is never imported by the controller."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class Generation(BaseModel):
    max_output_tokens: int | None = None
    temperature: float = 0.7


class WorkerInput(BaseModel):
    kind: str
    text: str | None = None
    messages: list[dict[str, str]] | None = None


class WorkerRequest(BaseModel):
    request_id: str
    input: WorkerInput
    generation: Generation


class NativeVLLM:
    def __init__(self) -> None:
        import os

        from transformers import AutoTokenizer
        from vllm.engine.arg_utils import AsyncEngineArgs
        from vllm.v1.engine.async_llm import AsyncLLM

        self.model = os.environ["RYUK_VLLM_MODEL"]
        self.revision = os.getenv("RYUK_VLLM_MODEL_REVISION")
        self.engine = AsyncLLM.from_engine_args(
            AsyncEngineArgs(
                model=self.model,
                revision=self.revision,
                tensor_parallel_size=int(
                    os.getenv("RYUK_VLLM_TENSOR_PARALLEL_SIZE", "1")
                ),
            )
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model, revision=self.revision
        )

    async def generate(self, request: WorkerRequest) -> dict[str, object]:
        from vllm import SamplingParams

        if request.input.kind == "text" and request.input.text is not None:
            prompt = request.input.text
        elif request.input.kind == "chat" and request.input.messages is not None:
            prompt = self.tokenizer.apply_chat_template(
                request.input.messages, tokenize=False, add_generation_prompt=True
            )
        else:
            raise HTTPException(422, "Invalid worker input.")
        sampling = SamplingParams(
            temperature=request.generation.temperature,
            max_tokens=request.generation.max_output_tokens or 128,
        )
        started = time.perf_counter()
        final = None
        async for output in self.engine.generate(prompt, sampling, request.request_id):
            final = output
        if final is None:
            raise HTTPException(502, "Engine returned no output.")
        completion = final.outputs[0]
        return {
            "text": completion.text,
            "finish_reason": completion.finish_reason or "unknown",
            "usage": {
                "input_tokens": len(final.prompt_token_ids),
                "output_tokens": len(completion.token_ids),
            },
            "latency_ms": (time.perf_counter() - started) * 1000,
            "metadata": {"runtime": "vllm", "vllm_request_id": request.request_id},
        }


worker: NativeVLLM | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker
    del app
    worker = NativeVLLM()
    yield
    if worker is not None:
        worker.engine.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/ryuk/v1/health")
async def health():
    return {"ready": worker is not None}


@app.get("/ryuk/v1/identity")
async def identity():
    if worker is None:
        raise HTTPException(503, "Worker is not ready.")
    import vllm

    return {
        "model_artifact_id": worker.model,
        "model_revision": worker.revision,
        "engine_version": vllm.__version__,
        "runtime": "async_llm",
    }


@app.post("/ryuk/v1/generate")
async def generate(request: WorkerRequest):
    if worker is None:
        raise HTTPException(503, "Worker is not ready.")
    return await worker.generate(request)


@app.delete("/ryuk/v1/requests/{request_id}")
async def cancel(request_id: str):
    if worker is None:
        raise HTTPException(503, "Worker is not ready.")
    await worker.engine.abort(request_id)
    return {"cancelled": True, "request_id": request_id}
